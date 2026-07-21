# app/api/dashboard.py
# Attendance summary/trend endpoints that power the student, teacher,
# and admin dashboards + charts. Read-only aggregation — no writes here.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from collections import defaultdict
from datetime import date as date_type, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.db.database import get_db
from app.models.db_models import User, Student, Batch, Period, Attendance
from app.api.deps import require_role

LOCAL_TZ = ZoneInfo("Asia/Kathmandu")
_WEEKDAY_MAP = {6: "SUNDAY", 0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY"}


def _today_local() -> date_type:
    return datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()


# ══════════════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════════════

class SubjectSummary(BaseModel):
    subject_id: int
    subject_code: str
    subject_name: str
    present_count: int
    absent_count: int
    total: int
    percentage: float


class OverallSummary(BaseModel):
    total_present: int
    total_absent: int
    total: int
    percentage: float
    by_subject: List[SubjectSummary]


class TrendPoint(BaseModel):
    date: str
    present_count: int
    absent_count: int
    percentage: float


class StudentRosterRow(BaseModel):
    student_id: int
    student_code: str
    student_name: str
    present_count: int
    absent_count: int
    total: int
    percentage: float


class TodayPeriod(BaseModel):
    period_id: int
    batch_id: int
    batch_name: str
    subject_id: int
    subject_code: str
    subject_name: str
    period_number: int
    start_time: str
    end_time: str


class AdminOverview(BaseModel):
    total_students: int
    total_teachers: int
    total_batches: int
    today_present_count: int
    today_absent_count: int
    overall_percentage_last_30_days: float


# ══════════════════════════════════════════════════════════════════════════
# Shared aggregation helpers (fetch + aggregate in Python — simple,
# correct, and plenty fast at school-project scale)
# ══════════════════════════════════════════════════════════════════════════

def _build_overall_summary(rows: List[Attendance]) -> OverallSummary:
    by_subject = defaultdict(lambda: {"present": 0, "absent": 0, "code": "", "name": ""})

    total_present = total_absent = 0
    for r in rows:
        subj = r.period.subject
        bucket = by_subject[subj.id]
        bucket["code"] = subj.subject_code
        bucket["name"] = subj.subject_name
        if r.status == "present":
            bucket["present"] += 1
            total_present += 1
        else:
            bucket["absent"] += 1
            total_absent += 1

    subject_summaries = []
    for subject_id, bucket in by_subject.items():
        total = bucket["present"] + bucket["absent"]
        pct = round((bucket["present"] / total) * 100, 1) if total else 0.0
        subject_summaries.append(SubjectSummary(
            subject_id=subject_id,
            subject_code=bucket["code"],
            subject_name=bucket["name"],
            present_count=bucket["present"],
            absent_count=bucket["absent"],
            total=total,
            percentage=pct,
        ))
    subject_summaries.sort(key=lambda s: s.subject_code)

    grand_total = total_present + total_absent
    overall_pct = round((total_present / grand_total) * 100, 1) if grand_total else 0.0

    return OverallSummary(
        total_present=total_present,
        total_absent=total_absent,
        total=grand_total,
        percentage=overall_pct,
        by_subject=subject_summaries,
    )


def _build_trend(rows: List[Attendance], days: int) -> List[TrendPoint]:
    by_date = defaultdict(lambda: {"present": 0, "absent": 0})
    for r in rows:
        bucket = by_date[r.date]
        if r.status == "present":
            bucket["present"] += 1
        else:
            bucket["absent"] += 1

    today = _today_local()
    points = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        bucket = by_date.get(d, {"present": 0, "absent": 0})
        total = bucket["present"] + bucket["absent"]
        pct = round((bucket["present"] / total) * 100, 1) if total else 0.0
        points.append(TrendPoint(
            date=d.isoformat(),
            present_count=bucket["present"],
            absent_count=bucket["absent"],
            percentage=pct,
        ))
    return points


# ══════════════════════════════════════════════════════════════════════════
# STUDENT dashboard
# ══════════════════════════════════════════════════════════════════════════

student_router = APIRouter(prefix="/student", dependencies=[Depends(require_role("student"))])


def _get_own_student_profile(current_user: User, db: Session) -> Student:
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="No student profile is linked to this account.")
    return student


@student_router.get("/me/summary", response_model=OverallSummary)
def my_summary(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    student = _get_own_student_profile(current_user, db)
    rows = db.query(Attendance).filter(Attendance.student_id == student.id).all()
    return _build_overall_summary(rows)


@student_router.get("/me/trend", response_model=List[TrendPoint])
def my_trend(
    days: int = 30,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    student = _get_own_student_profile(current_user, db)
    cutoff = _today_local() - timedelta(days=days)
    rows = (
        db.query(Attendance)
          .filter(Attendance.student_id == student.id, Attendance.date >= cutoff)
          .all()
    )
    return _build_trend(rows, days)


@student_router.get("/me/history")
def my_history(
    limit: int = 100,
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    student = _get_own_student_profile(current_user, db)
    rows = (
        db.query(Attendance)
          .filter(Attendance.student_id == student.id)
          .order_by(Attendance.date.desc(), Attendance.timestamp.desc())
          .limit(limit)
          .all()
    )
    return [
        {
            "date": r.date.isoformat(),
            "subject_code": r.period.subject.subject_code,
            "subject_name": r.period.subject.subject_name,
            "status": r.status,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════════════
# TEACHER dashboard
# ══════════════════════════════════════════════════════════════════════════

teacher_router = APIRouter(prefix="/teacher", dependencies=[Depends(require_role("teacher", "admin"))])


def _teacher_owns_batch(db: Session, teacher_id: int, batch_id: int) -> bool:
    return db.query(Period).filter(Period.teacher_id == teacher_id, Period.batch_id == batch_id).first() is not None


@teacher_router.get("/me/today", response_model=List[TodayPeriod])
def my_today(
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    now_local = datetime.now(timezone.utc).astimezone(LOCAL_TZ)
    day = _WEEKDAY_MAP.get(now_local.weekday())
    if day is None:
        return []  # weekend

    periods = (
        db.query(Period)
          .filter(Period.teacher_id == current_user.id, Period.day_of_week == day)
          .order_by(Period.period_number)
          .all()
    )
    return [
        TodayPeriod(
            period_id=p.id, batch_id=p.batch_id, batch_name=p.batch.batch_name,
            subject_id=p.subject_id, subject_code=p.subject.subject_code,
            subject_name=p.subject.subject_name, period_number=p.period_number,
            start_time=p.slot.start_time.strftime("%H:%M"),
            end_time=p.slot.end_time.strftime("%H:%M"),
        )
        for p in periods
    ]


@teacher_router.get("/me/batches", response_model=List[dict])
def my_batches(
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    periods = db.query(Period).filter(Period.teacher_id == current_user.id).all()
    seen = {}
    for p in periods:
        seen[p.batch_id] = p.batch.batch_name
    return [{"batch_id": bid, "batch_name": name} for bid, name in seen.items()]


def _compute_roster(
    db: Session, batch_id: int, subject_id: Optional[int],
    start_date: Optional[date_type], end_date: Optional[date_type],
) -> List[StudentRosterRow]:
    if not db.query(Batch).filter(Batch.id == batch_id).first():
        raise HTTPException(status_code=404, detail="Batch not found.")

    students = db.query(Student).filter(Student.batch_id == batch_id).all()

    rows_by_student = defaultdict(list)
    query = db.query(Attendance).join(Period).filter(Period.batch_id == batch_id)
    if subject_id:
        query = query.filter(Period.subject_id == subject_id)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)

    for r in query.all():
        rows_by_student[r.student_id].append(r)

    out = []
    for s in students:
        rows = rows_by_student.get(s.id, [])
        present = sum(1 for r in rows if r.status == "present")
        total = len(rows)
        pct = round((present / total) * 100, 1) if total else 0.0
        out.append(StudentRosterRow(
            student_id=s.id, student_code=s.student_code, student_name=s.student_name,
            present_count=present, absent_count=total - present, total=total, percentage=pct,
        ))

    out.sort(key=lambda r: r.student_name)
    return out


@teacher_router.get("/batch/{batch_id}/roster", response_model=List[StudentRosterRow])
def batch_roster_summary(
    batch_id: int,
    subject_id: Optional[int] = None,
    start_date: Optional[date_type] = None,
    end_date: Optional[date_type] = None,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    if current_user.role == "teacher" and not _teacher_owns_batch(db, current_user.id, batch_id):
        raise HTTPException(status_code=403, detail="You don't teach this batch.")

    return _compute_roster(db, batch_id, subject_id, start_date, end_date)


@teacher_router.get("/batch/{batch_id}/trend", response_model=List[TrendPoint])
def batch_trend(
    batch_id: int,
    days: int = 30,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    if current_user.role == "teacher" and not _teacher_owns_batch(db, current_user.id, batch_id):
        raise HTTPException(status_code=403, detail="You don't teach this batch.")

    cutoff = _today_local() - timedelta(days=days)
    rows = (
        db.query(Attendance)
          .join(Period)
          .filter(Period.batch_id == batch_id, Attendance.date >= cutoff)
          .all()
    )
    return _build_trend(rows, days)


# ══════════════════════════════════════════════════════════════════════════
# ADMIN dashboard (same "/admin" prefix as admin.py — different paths)
# ══════════════════════════════════════════════════════════════════════════

admin_dashboard_router = APIRouter(prefix="/admin", dependencies=[Depends(require_role("admin"))])


@admin_dashboard_router.get("/overview", response_model=AdminOverview)
def admin_overview(db: Session = Depends(get_db)):
    total_students = db.query(Student).count()
    total_teachers = db.query(User).filter(User.role == "teacher").count()
    total_batches = db.query(Batch).count()

    today = _today_local()
    today_rows = db.query(Attendance).filter(Attendance.date == today).all()
    today_present = sum(1 for r in today_rows if r.status == "present")
    today_absent = sum(1 for r in today_rows if r.status == "absent")

    cutoff = today - timedelta(days=30)
    recent_rows = db.query(Attendance).filter(Attendance.date >= cutoff).all()
    recent_present = sum(1 for r in recent_rows if r.status == "present")
    recent_total = len(recent_rows)
    overall_pct = round((recent_present / recent_total) * 100, 1) if recent_total else 0.0

    return AdminOverview(
        total_students=total_students,
        total_teachers=total_teachers,
        total_batches=total_batches,
        today_present_count=today_present,
        today_absent_count=today_absent,
        overall_percentage_last_30_days=overall_pct,
    )


@admin_dashboard_router.get("/batch/{batch_id}/roster", response_model=List[StudentRosterRow])
def admin_batch_roster(
    batch_id: int,
    subject_id: Optional[int] = None,
    start_date: Optional[date_type] = None,
    end_date: Optional[date_type] = None,
    db: Session = Depends(get_db),
):
    # Admin can view any batch — no ownership check needed since the
    # "admin" role dependency on this router already gates access.
    return _compute_roster(db, batch_id, subject_id, start_date, end_date)