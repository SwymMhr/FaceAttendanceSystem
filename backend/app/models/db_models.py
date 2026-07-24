# app/models/db_models.py
# These Python classes define your database tables (matches reset_schema.sql).

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, Time, DateTime,
    ForeignKey, ForeignKeyConstraint, Text, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.database import Base


class User(Base):
    __tablename__ = "tbl_users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, nullable=False, default="student")
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Display name for teacher/admin accounts (students don't need this —
    # their name lives on tbl_students.student_name, which is the roster's
    # source of truth). Nullable because student accounts leave it unset.
    full_name     = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint("role IN ('student','teacher','admin')", name="ck_users_role"),
    )

    student_profile = relationship("Student", back_populates="user", uselist=False)
    # teacher_id has ON DELETE CASCADE at the DB level (see reset_schema.sql).
    # passive_deletes=True tells SQLAlchemy to let Postgres handle removing
    # these rows itself instead of first trying to null out teacher_id —
    # which would fail, since that column is NOT NULL.
    periods_taught  = relationship("Period", back_populates="teacher", passive_deletes=True)


class Batch(Base):
    """A cohort, e.g. '2022 Civil', '2024 Software'."""
    __tablename__ = "tbl_batches"

    id         = Column(Integer, primary_key=True, index=True)
    batch_name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    students = relationship("Student", back_populates="batch")
    # batch_id has ON DELETE CASCADE at the DB level, which itself cascades
    # further into tbl_attendance (period_id is also ON DELETE CASCADE).
    # passive_deletes=True lets Postgres run that whole chain in one
    # statement instead of SQLAlchemy trying to manage each level itself.
    periods      = relationship("Period", back_populates="batch", passive_deletes=True)
    period_slots = relationship("PeriodSlot", back_populates="batch", passive_deletes=True)


class Student(Base):
    __tablename__ = "tbl_students"

    id           = Column(Integer, primary_key=True, index=True)
    student_code = Column(String, unique=True, index=True, nullable=False)
    student_name = Column(String, nullable=False)
    user_id      = Column(Integer, ForeignKey("tbl_users.id", ondelete="SET NULL"), unique=True, nullable=True)
    batch_id     = Column(Integer, ForeignKey("tbl_batches.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user        = relationship("User", back_populates="student_profile")
    batch       = relationship("Batch", back_populates="students")
    # Both FKs are ON DELETE CASCADE at the DB level — let Postgres handle
    # cleanup instead of SQLAlchemy managing it row-by-row in the ORM.
    embeddings  = relationship("Embedding", back_populates="student", passive_deletes=True)
    attendances = relationship("Attendance", back_populates="student", passive_deletes=True)


class Embedding(Base):
    __tablename__ = "tbl_embeddings"

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("tbl_students.id", ondelete="CASCADE"), nullable=False)
    vector     = Column(Text, nullable=False)
    image_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="embeddings")


class Subject(Base):
    __tablename__ = "tbl_subjects"

    id           = Column(Integer, primary_key=True, index=True)
    subject_code = Column(String, unique=True, nullable=False)  # e.g. "CE101"
    subject_name = Column(String, unique=True, nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    periods = relationship("Period", back_populates="subject")


class PeriodSlot(Base):
    """
    A batch's own daily period times — e.g. Batch A's period #1 might be
    07:00-08:45 while Batch B's period #1 is 09:00-10:00. Each batch
    defines its own set of slots (however many it needs) through the
    admin UI instead of everyone sharing 4 fixed global times.
    """
    __tablename__ = "tbl_period_slots"

    id            = Column(Integer, primary_key=True, index=True)
    batch_id      = Column(Integer, ForeignKey("tbl_batches.id", ondelete="CASCADE"), nullable=False)
    period_number = Column(Integer, nullable=False)  # scoped to batch_id, not global — 1..N per batch
    start_time    = Column(Time, nullable=False)
    end_time      = Column(Time, nullable=False)

    __table_args__ = (
        UniqueConstraint("batch_id", "period_number", name="uq_batch_period_number"),
        CheckConstraint("end_time > start_time", name="ck_slot_time_order"),
    )

    batch   = relationship("Batch", back_populates="period_slots")
    periods = relationship("Period", back_populates="slot")


class Period(Base):
    """
    THE timetable engine. One row = this batch, on this weekday, in this
    slot, teaching this subject, taught by this teacher.

    period_number now only means something in combination with batch_id
    (see PeriodSlot) — two different batches can have completely
    different clock times for "period #1". Because of that, teacher
    double-booking can no longer be checked with a simple unique
    constraint (same period_number across batches might not be the same
    real time, and different period_numbers might overlap) — that check
    now happens in application code (see schedule.py's _check_conflicts),
    comparing each candidate slot's actual start/end time.
    """
    __tablename__ = "tbl_periods"

    id            = Column(Integer, primary_key=True, index=True)
    batch_id      = Column(Integer, ForeignKey("tbl_batches.id", ondelete="CASCADE"), nullable=False)
    subject_id    = Column(Integer, ForeignKey("tbl_subjects.id", ondelete="CASCADE"), nullable=False)
    teacher_id    = Column(Integer, ForeignKey("tbl_users.id", ondelete="CASCADE"), nullable=False)
    period_number = Column(Integer, nullable=False)
    day_of_week   = Column(String, nullable=False)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "day_of_week IN ('SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY')",
            name="ck_period_weekday",
        ),
        UniqueConstraint("batch_id", "day_of_week", "period_number", name="uq_batch_slot"),
        # Composite FK instead of a plain one on period_number alone — this
        # is what actually enforces "this period's slot must belong to
        # this same batch" at the database level.
        ForeignKeyConstraint(
            ["batch_id", "period_number"],
            ["tbl_period_slots.batch_id", "tbl_period_slots.period_number"],
            ondelete="CASCADE",
            name="fk_periods_batch_slot",
        ),
    )

    batch       = relationship("Batch", back_populates="periods")
    subject     = relationship("Subject", back_populates="periods")
    teacher     = relationship("User", back_populates="periods_taught")
    slot        = relationship("PeriodSlot", back_populates="periods")
    # period_id has ON DELETE CASCADE at the DB level (see reset_schema.sql).
    # passive_deletes=True tells SQLAlchemy to let Postgres remove these rows
    # itself instead of first trying to null out period_id — which would
    # fail, since that column is NOT NULL.
    attendances = relationship("Attendance", back_populates="period", passive_deletes=True)


class Attendance(Base):
    """
    One row = one student's outcome for one period-instance on one date.
    Absence emails are sent directly from the backfill job at write time
    (see app/services/notify.py) — there's no notifications table; this
    row is the only persisted record of the event.
    """
    __tablename__ = "tbl_attendance"

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("tbl_students.id", ondelete="CASCADE"), nullable=False)
    period_id  = Column(Integer, ForeignKey("tbl_periods.id", ondelete="CASCADE"), nullable=False)
    date       = Column(Date, nullable=False)
    status     = Column(String, nullable=False, default="present")
    confidence = Column(Float, nullable=True)
    timestamp  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # 'pending' = a face was auto-recognized by the camera but a teacher
        # hasn't confirmed it yet. It's never a terminal state on its own —
        # it always resolves to 'present' or 'absent' via teacher review or
        # the end-of-day auto-finalize (see absence_service.py).
        CheckConstraint("status IN ('present','absent','pending')", name="ck_attendance_status"),
        UniqueConstraint("student_id", "period_id", "date", name="uq_attendance_slot"),
    )

    student = relationship("Student", back_populates="attendances")
    period  = relationship("Period", back_populates="attendances")