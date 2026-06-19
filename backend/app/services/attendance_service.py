from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_

from app.models.db_models import Attendance, Student


def mark_attendance_logic(db: Session, student_id: int, confidence: float):

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    # prevent duplicate attendance within 1 day
    today = datetime.now(timezone.utc) - timedelta(days=1)

    recent = db.query(Attendance).filter(
        and_(
            Attendance.student_id == student.id,
            Attendance.timestamp >= today
        )
    ).first()

    if recent:
        return {"status": "skipped"}

    record = Attendance(
        student_id=student.id,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "status": "marked",
        "record": record
    }