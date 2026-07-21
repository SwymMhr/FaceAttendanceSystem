# app/services/absence_service.py
# After a period ends, compares its batch roster against who has a
# "present" row for that period+date, backfills "absent" rows for
# everyone else, and emails each of them once.

from datetime import date as date_type, datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.db_models import Period, Student, Attendance
from app.services.notify import send_absence_email

LOCAL_TZ = ZoneInfo("Asia/Kathmandu")


def finalize_period_absentees(db: Session, period_id: int, target_date: date_type | None = None) -> dict:
    """
    Idempotent — safe to call more than once for the same period+date.
    Only students with no attendance row at all for that period+date get
    a new "absent" row and an email; anyone already processed (present
    OR previously backfilled absent) is left untouched.
    """
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise ValueError(f"Period {period_id} not found.")

    target_date = target_date or datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()

    roster = db.query(Student).filter(Student.batch_id == period.batch_id).all()

    already_recorded_ids = {
        row.student_id
        for row in db.query(Attendance).filter(
            Attendance.period_id == period.id,
            Attendance.date == target_date,
        ).all()
    }

    newly_absent_students = []

    for student in roster:
        if student.id in already_recorded_ids:
            continue  # already present or already backfilled absent

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
        "newly_marked_absent": [s.student_name for s in newly_absent_students],
    }