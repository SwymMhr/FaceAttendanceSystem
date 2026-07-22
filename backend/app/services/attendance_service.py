# app/services/attendance_service.py
# Marks a student "pending" for whichever period is currently in session
# for their batch, whenever the camera recognizes them — it does NOT write
# "present" directly anymore. A teacher has to confirm (or the end-of-day
# auto-finalize has to run) before a detection counts as present. Attendance
# is always tied to a real period_id + date.

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

    A camera match no longer writes "present" straight to the database —
    it records a "pending" row that a teacher has to review. The teacher
    then confirms it as present, rejects it as absent, or it gets
    auto-confirmed present at end of day if nobody touches it
    (see absence_service.finalize_period_absentees).
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
        if existing.status == "pending":
            return {
                "status": "skipped",
                "message": f"Already awaiting teacher confirmation for {period.subject.subject_name} today.",
                "student": student.student_name,
            }
        return {
            "status": "skipped",
            "message": f"Already marked {existing.status} for {period.subject.subject_name} today.",
            "student": student.student_name,
        }

    record = Attendance(
        student_id=student.id,
        period_id=period.id,
        date=today_local,
        status="pending",
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "status": "pending",
        "message": "Face recognized — awaiting teacher confirmation.",
        "student": student.student_name,
        "subject": period.subject.subject_name,
        "timestamp": record.timestamp.isoformat(),
    }


def set_attendance_status(
    db: Session,
    student_id: int,
    period_id: int,
    target_date,
    status: str,
    confidence: float | None = None,
) -> Attendance:
    """
    Teacher-driven override: create or update the attendance row for
    (student, period, date) to an explicit status ("present" or "absent").

    Used for:
      - confirming a pending camera detection ("present")
      - rejecting a pending camera detection ("absent")
      - forcing attendance for a student the camera never detected at all
    Always wins over whatever was there before (including a prior
    confirm/reject), since it's an explicit teacher decision.
    """
    if status not in ("present", "absent"):
        raise ValueError("status must be 'present' or 'absent'.")

    record = (
        db.query(Attendance)
          .filter(
              Attendance.student_id == student_id,
              Attendance.period_id == period_id,
              Attendance.date == target_date,
          )
          .first()
    )

    if record:
        record.status = status
        if confidence is not None:
            record.confidence = confidence
    else:
        record = Attendance(
            student_id=student_id,
            period_id=period_id,
            date=target_date,
            status=status,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record