# app/services/attendance_service.py
# Marks a student "present" for whichever period is currently in session
# for their batch. Replaces the old confidence-only insert — attendance
# is now always tied to a real period_id + date.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.db_models import Student, Period, PeriodSlot, Attendance

# All period times (7:00-14:30) are defined in local wall-clock time.
LOCAL_TZ = ZoneInfo("Asia/Kathmandu")

# Python's date.weekday(): Monday=0 ... Sunday=6
_WEEKDAY_MAP = {6: "SUNDAY", 0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY"}
# Friday=4, Saturday=5 intentionally absent — those are weekends, no periods run.


def get_current_period(db: Session, batch_id: int, at: datetime | None = None) -> Period | None:
    """
    Returns the Period row that's actually in session right now for this
    batch, or None if it's a weekend, outside school hours, or during the
    mid-day break — in all of which cases nothing should be marked.
    """
    now_local = (at or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)

    day = _WEEKDAY_MAP.get(now_local.weekday())
    if day is None:
        return None  # Friday/Saturday

    current_time = now_local.time()
    slot = (
        db.query(PeriodSlot)
          .filter(PeriodSlot.start_time <= current_time, PeriodSlot.end_time > current_time)
          .first()
    )
    if not slot:
        return None  # before 7:00, after 14:30, or in the 10:30-11:00 break

    return (
        db.query(Period)
          .filter(
              Period.batch_id == batch_id,
              Period.day_of_week == day,
              Period.period_number == slot.period_number,
          )
          .first()
    )


def mark_attendance_logic(db: Session, student_id: int, confidence: float) -> dict:
    """
    Called from both /mark_attendance and /process_frame with the same
    signature (db, student_id, confidence) they already use.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {"status": "error", "message": "Student not found."}

    if not student.batch_id:
        return {"status": "error", "message": f"{student.student_name} is not assigned to any batch."}

    period = get_current_period(db, student.batch_id)
    if not period:
        return {
            "status": "skipped",
            "message": "No class is currently in session for this student's batch.",
            "student": student.student_name,
        }

    today_local = datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()

    existing = (
        db.query(Attendance)
          .filter(
              Attendance.student_id == student.id,
              Attendance.period_id == period.id,
              Attendance.date == today_local,
          )
          .first()
    )
    if existing:
        return {
            "status": "skipped",
            "message": f"Already marked present for {period.subject.subject_name} today.",
            "student": student.student_name,
        }

    record = Attendance(
        student_id=student.id,
        period_id=period.id,
        date=today_local,
        status="present",
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "status": "marked",
        "message": "Attendance marked.",
        "student": student.student_name,
        "subject": period.subject.subject_name,
        "timestamp": record.timestamp.isoformat(),
    }