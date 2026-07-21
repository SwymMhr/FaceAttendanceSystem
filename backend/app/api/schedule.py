# app/api/schedule.py
# Admin-only endpoints for building each batch's weekly timetable:
# assigning a subject + teacher to a (batch, day, period_number) slot.
# All routes require role == "admin".

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional, List

from app.db.database import get_db
from app.models.db_models import Period, PeriodSlot, Batch, Subject, User
from app.api.deps import require_role

router = APIRouter(prefix="/admin", dependencies=[Depends(require_role("admin"))])

ALLOWED_DAYS = ("SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY")


# ══════════════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════════════

class PeriodCreate(BaseModel):
    batch_id: int
    subject_id: int
    teacher_id: int
    day_of_week: str
    period_number: int

    @field_validator("day_of_week")
    @classmethod
    def check_day(cls, v):
        v = v.upper()
        if v not in ALLOWED_DAYS:
            raise ValueError(f"day_of_week must be one of {ALLOWED_DAYS} (Friday/Saturday are weekends)")
        return v

    @field_validator("period_number")
    @classmethod
    def check_period_number(cls, v):
        if v not in (1, 2, 3, 4):
            raise ValueError("period_number must be 1, 2, 3, or 4")
        return v


class PeriodOut(BaseModel):
    id: int
    batch_id: int
    batch_name: str
    subject_id: int
    subject_code: str
    subject_name: str
    teacher_id: int
    teacher_name: str
    day_of_week: str
    period_number: int
    start_time: str
    end_time: str


class PeriodSlotOut(BaseModel):
    period_number: int
    start_time: str
    end_time: str


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _to_period_out(p: Period) -> PeriodOut:
    return PeriodOut(
        id=p.id,
        batch_id=p.batch_id,
        batch_name=p.batch.batch_name,
        subject_id=p.subject_id,
        subject_code=p.subject.subject_code,
        subject_name=p.subject.subject_name,
        teacher_id=p.teacher_id,
        teacher_name=p.teacher.user_name,
        day_of_week=p.day_of_week,
        period_number=p.period_number,
        start_time=p.slot.start_time.strftime("%H:%M"),
        end_time=p.slot.end_time.strftime("%H:%M"),
    )


def _check_conflicts(db: Session, batch_id: int, teacher_id: int, day_of_week: str,
                      period_number: int, exclude_period_id: Optional[int] = None):
    """Raise a clear 409 if this slot is already taken, either for the
    batch (two subjects at once) or the teacher (double-booked)."""

    batch_conflict = db.query(Period).filter(
        Period.batch_id == batch_id,
        Period.day_of_week == day_of_week,
        Period.period_number == period_number,
    )
    if exclude_period_id:
        batch_conflict = batch_conflict.filter(Period.id != exclude_period_id)
    existing = batch_conflict.first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This batch already has '{existing.subject.subject_name}' in that slot on {day_of_week}.",
        )

    teacher_conflict = db.query(Period).filter(
        Period.teacher_id == teacher_id,
        Period.day_of_week == day_of_week,
        Period.period_number == period_number,
    )
    if exclude_period_id:
        teacher_conflict = teacher_conflict.filter(Period.id != exclude_period_id)
    existing = teacher_conflict.first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This teacher is already teaching '{existing.subject.subject_name}' to "
                f"'{existing.batch.batch_name}' in that slot on {day_of_week}."
            ),
        )


# ══════════════════════════════════════════════════════════════════════════
# Period slots (read-only reference — the 4 fixed times)
# ══════════════════════════════════════════════════════════════════════════

@router.get("/period-slots", response_model=List[PeriodSlotOut])
def list_period_slots(db: Session = Depends(get_db)):
    slots = db.query(PeriodSlot).order_by(PeriodSlot.period_number).all()
    return [
        PeriodSlotOut(
            period_number=s.period_number,
            start_time=s.start_time.strftime("%H:%M"),
            end_time=s.end_time.strftime("%H:%M"),
        )
        for s in slots
    ]


# ══════════════════════════════════════════════════════════════════════════
# Periods (the actual timetable entries)
# ══════════════════════════════════════════════════════════════════════════

@router.post("/periods", response_model=PeriodOut)
def create_period(payload: PeriodCreate, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    teacher = db.query(User).filter(User.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    if teacher.role != "teacher":
        raise HTTPException(status_code=400, detail="Assigned user must have the 'teacher' role.")

    _check_conflicts(db, payload.batch_id, payload.teacher_id, payload.day_of_week, payload.period_number)

    period = Period(
        batch_id=payload.batch_id,
        subject_id=payload.subject_id,
        teacher_id=payload.teacher_id,
        day_of_week=payload.day_of_week,
        period_number=payload.period_number,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return _to_period_out(period)


@router.get("/periods", response_model=List[PeriodOut])
def list_periods(
    batch_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    day_of_week: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Period)
    if batch_id:
        query = query.filter(Period.batch_id == batch_id)
    if teacher_id:
        query = query.filter(Period.teacher_id == teacher_id)
    if day_of_week:
        query = query.filter(Period.day_of_week == day_of_week.upper())

    periods = query.order_by(Period.day_of_week, Period.period_number).all()
    return [_to_period_out(p) for p in periods]


@router.get("/periods/timetable/{batch_id}", response_model=List[PeriodOut])
def get_batch_timetable(batch_id: int, db: Session = Depends(get_db)):
    """Convenience endpoint: full weekly timetable for one batch,
    ready to render as a day x period grid on the frontend."""
    if not db.query(Batch).filter(Batch.id == batch_id).first():
        raise HTTPException(status_code=404, detail="Batch not found.")

    periods = (
        db.query(Period)
          .filter(Period.batch_id == batch_id)
          .order_by(Period.day_of_week, Period.period_number)
          .all()
    )
    return [_to_period_out(p) for p in periods]


@router.put("/periods/{period_id}", response_model=PeriodOut)
def update_period(period_id: int, payload: PeriodCreate, db: Session = Depends(get_db)):
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found.")

    if not db.query(Batch).filter(Batch.id == payload.batch_id).first():
        raise HTTPException(status_code=404, detail="Batch not found.")
    if not db.query(Subject).filter(Subject.id == payload.subject_id).first():
        raise HTTPException(status_code=404, detail="Subject not found.")
    teacher = db.query(User).filter(User.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    if teacher.role != "teacher":
        raise HTTPException(status_code=400, detail="Assigned user must have the 'teacher' role.")

    _check_conflicts(
        db, payload.batch_id, payload.teacher_id, payload.day_of_week,
        payload.period_number, exclude_period_id=period_id,
    )

    period.batch_id = payload.batch_id
    period.subject_id = payload.subject_id
    period.teacher_id = payload.teacher_id
    period.day_of_week = payload.day_of_week
    period.period_number = payload.period_number

    db.commit()
    db.refresh(period)
    return _to_period_out(period)


@router.delete("/periods/{period_id}")
def delete_period(period_id: int, db: Session = Depends(get_db)):
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found.")

    db.delete(period)
    db.commit()
    return {"message": "Period removed from timetable."}