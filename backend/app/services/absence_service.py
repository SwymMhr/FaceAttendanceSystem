# app/services/absence_service.py
# This is the "close out the day" step for one period. It:
#   1. Auto-confirms any lingering "pending" camera detections as "present"
#      — a teacher had the whole day to review/reject them and didn't, so
#      the detection stands.
#   2. Compares the batch roster against who now has a "present" row for
#      that period+date, backfills "absent" rows for everyone else, and
#      emails each of them once.
# Runs either on-demand (teacher clicks "Finalize Attendance") or
# automatically at end of day via the scheduler.

from datetime import date as date_type, datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.db_models import Period, Student, Attendance
from app.services.notify import send_absence_email

LOCAL_TZ = ZoneInfo("Asia/Kathmandu")


def finalize_period_absentees(db: Session, period_id: int, target_date: date_type | None = None) -> dict:
    """
    Idempotent — safe to call more than once for the same period+date.

    Step 1: any row still "pending" (camera detected them, nobody
    confirmed or rejected it) is auto-confirmed to "present".
    Step 2: students with no attendance row at all get a new "absent"
    row and an email. Anyone already "present" or "absent" (whether set
    by a teacher, auto-confirmed above, or from a previous run of this
    function) is left untouched.
    """
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise ValueError(f"Period {period_id} not found.")

    target_date = target_date or datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()

    roster = db.query(Student).filter(Student.batch_id == period.batch_id).all()

    existing_rows = (
        db.query(Attendance)
          .filter(Attendance.period_id == period.id, Attendance.date == target_date)
          .all()
    )

    # Step 1 — auto-confirm lingering pending detections as present.
    auto_confirmed_students = []
    for row in existing_rows:
        if row.status == "pending":
            row.status = "present"
            auto_confirmed_students.append(row.student)
    if auto_confirmed_students:
        db.commit()

    already_recorded_ids = {row.student_id for row in existing_rows}

    # Step 2 — backfill absent for anyone with no row at all.
    newly_absent_students = []
    for student in roster:
        if student.id in already_recorded_ids:
            continue  # present (teacher-marked or auto-confirmed) or already absent

        record = Attendance(
            student_id=student.id,
            period_id=period.id,
            date=target_date,
            status="absent",
            confidence=None,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(record)
        newly_absent_students.append(student)

    db.commit()

    for student in newly_absent_students:
        if student.user and student.user.email:
            send_absence_email(
                to_email=student.user.email,
                student_name=student.student_name,
                subject_name=period.subject.subject_name,
                on_date=target_date,
            )

    return {
        "period_id": period.id,
        "batch_name": period.batch.batch_name,
        "subject_name": period.subject.subject_name,
        "date": target_date.isoformat(),
        "auto_confirmed_present": [s.student_name for s in auto_confirmed_students],
        "newly_marked_absent": [s.student_name for s in newly_absent_students],
    }