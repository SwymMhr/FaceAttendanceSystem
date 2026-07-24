# app/api/schedule.py
# Admin-only endpoints for building each batch's weekly timetable:
# assigning a subject + teacher to a (batch, day, period_number) slot.
# All routes require role == "admin".

from datetime import time as time_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional, List

from app.db.database import get_db
from app.models.db_models import Period, PeriodSlot, Batch, Subject, User
from app.api.deps import require_role

router = APIRouter(prefix="/admin", dependencies=[Depends(require_role("admin"))])

ALLOWED_DAYS = ("SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")


# ══════════════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════════════

class PeriodCreate(BaseModel):
    batch_id: int
    subject_id: int
    teacher_id: int
    day_of_week: str
    period_number: int  # must reference a slot already defined for this batch

    @field_validator("day_of_week")
    @classmethod
    def check_day(cls, v):
        v = v.upper()
        if v not in ALLOWED_DAYS:
            raise ValueError(f"day_of_week must be one of {ALLOWED_DAYS} (Saturday is the weekend)")
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


class PeriodSlotCreate(BaseModel):
    start_time: str  # "HH:MM"
    end_time: str     # "HH:MM"

    @field_validator("start_time", "end_time")
    @classmethod
    def check_hhmm(cls, v):
        try:
            hh, mm = v.split(":")
            time_type(int(hh), int(mm))
        except Exception:
            raise ValueError("Time must be in HH:MM 24-hour format, e.g. '07:00'.")
        return v


class PeriodSlotOut(BaseModel):
    id: int
    batch_id: int
    period_number: int
    start_time: str
    end_time: str


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _parse_hhmm(v: str) -> time_type:
    hh, mm = v.split(":")
    return time_type(int(hh), int(mm))


def _to_period_out(p: Period) -> PeriodOut:
    return PeriodOut(
        id=p.id,
        batch_id=p.batch_id,
        batch_name=p.batch.batch_name,
        subject_id=p.subject_id,
        subject_code=p.subject.subject_code,
        subject_name=p.subject.subject_name,
        teacher_id=p.teacher_id,
        teacher_name=p.teacher.full_name or p.teacher.email,
        day_of_week=p.day_of_week,
        period_number=p.period_number,
        start_time=p.slot.start_time.strftime("%H:%M"),
        end_time=p.slot.end_time.strftime("%H:%M"),
    )


def _get_slot_or_404(db: Session, batch_id: int, period_number: int) -> PeriodSlot:
    slot = (
        db.query(PeriodSlot)
          .filter(PeriodSlot.batch_id == batch_id, PeriodSlot.period_number == period_number)
          .first()
    )
    if not slot:
        raise HTTPException(
            status_code=404,
            detail=f"No period slot #{period_number} defined for this batch yet — add one first.",
        )
    return slot


def _check_conflicts(db: Session, batch_id: int, teacher_id: int, day_of_week: str,
                      period_number: int, exclude_period_id: Optional[int] = None):
    """Raise a clear 409 if this slot is already taken, either for the
    batch (two subjects at once) or the teacher (double-booked).

    Batch conflicts are still a simple (batch_id, day, period_number)
    lookup. Teacher conflicts can no longer be — since each batch now
    defines its own slot times, "period #2" in one batch might be a
    completely different clock-time window than "period #2" in another.
    So teacher double-booking is checked by comparing actual start/end
    times against every other period that teacher has that day, across
    all batches.
    """
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

    new_slot = _get_slot_or_404(db, batch_id, period_number)

    teacher_periods = db.query(Period).filter(
        Period.teacher_id == teacher_id,
        Period.day_of_week == day_of_week,
    )
    if exclude_period_id:
        teacher_periods = teacher_periods.filter(Period.id != exclude_period_id)

    for other in teacher_periods.all():
        other_slot = (
            db.query(PeriodSlot)
              .filter(PeriodSlot.batch_id == other.batch_id, PeriodSlot.period_number == other.period_number)
              .first()
        )
        if not other_slot:
            continue
        # Standard interval overlap test: two ranges overlap if each
        # starts before the other ends.
        if new_slot.start_time < other_slot.end_time and other_slot.start_time < new_slot.end_time:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This teacher is already teaching '{other.subject.subject_name}' to "
                    f"'{other.batch.batch_name}' from {other_slot.start_time.strftime('%H:%M')}"
                    f"–{other_slot.end_time.strftime('%H:%M')} on {day_of_week}, which overlaps this slot."
                ),
            )


# ══════════════════════════════════════════════════════════════════════════
# Period slots — each batch's own editable set of period times
# ══════════════════════════════════════════════════════════════════════════

@router.get("/batches/{batch_id}/period-slots", response_model=List[PeriodSlotOut])
def list_batch_period_slots(batch_id: int, db: Session = Depends(get_db)):
    if not db.query(Batch).filter(Batch.id == batch_id).first():
        raise HTTPException(status_code=404, detail="Batch not found.")

    slots = (
        db.query(PeriodSlot)
          .filter(PeriodSlot.batch_id == batch_id)
          .order_by(PeriodSlot.period_number)
          .all()
    )
    return [
        PeriodSlotOut(
            id=s.id, batch_id=s.batch_id, period_number=s.period_number,
            start_time=s.start_time.strftime("%H:%M"),
            end_time=s.end_time.strftime("%H:%M"),
        )
        for s in slots
    ]


@router.post("/batches/{batch_id}/period-slots", response_model=PeriodSlotOut)
def create_batch_period_slot(batch_id: int, payload: PeriodSlotCreate, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    start_time = _parse_hhmm(payload.start_time)
    end_time = _parse_hhmm(payload.end_time)
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")

    # Auto-number: next period for this batch, so the admin never has to
    # pick a period_number by hand or risk colliding with an existing one.
    last = (
        db.query(PeriodSlot)
          .filter(PeriodSlot.batch_id == batch_id)
          .order_by(PeriodSlot.period_number.desc())
          .first()
    )
    next_number = (last.period_number + 1) if last else 1

    slot = PeriodSlot(
        batch_id=batch_id,
        period_number=next_number,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    return PeriodSlotOut(
        id=slot.id, batch_id=slot.batch_id, period_number=slot.period_number,
        start_time=slot.start_time.strftime("%H:%M"),
        end_time=slot.end_time.strftime("%H:%M"),
    )


@router.delete("/period-slots/{slot_id}")
def delete_period_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(PeriodSlot).filter(PeriodSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Period slot not found.")

    # Cascades at the DB level (fk_periods_batch_slot ON DELETE CASCADE):
    # deleting a slot also deletes every period assigned into it, across
    # the whole week. That's an intentional, if blunt, tool — the frontend
    # should warn before calling this if the slot is in use.
    db.delete(slot)
    db.commit()
    return {"message": "Period slot removed."}


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

    _get_slot_or_404(db, payload.batch_id, payload.period_number)
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

    _get_slot_or_404(db, payload.batch_id, payload.period_number)
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