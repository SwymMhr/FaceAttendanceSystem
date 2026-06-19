# app/models/db_models.py
# These Python classes define your 3 database tables.
# SQLAlchemy will translate them into actual PostgreSQL tables.

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.database import Base


class Student(Base):
    """
    The `students` table.
    Stores basic info about each enrolled student.
    """
    __tablename__ = "students"

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True, nullable=False)  # e.g. "STU001"
    name       = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # One student → many embeddings (one per uploaded photo)
    embeddings  = relationship("Embedding", back_populates="student", cascade="all, delete")
    # One student → many attendance records
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete")


class Embedding(Base):
    """
    The `embeddings` table.
    Each row stores a 128-dimensional embedding vector for one uploaded face image.
    We store the 128 floats as a comma-separated string (simple & portable).
    """
    __tablename__ = "embeddings"

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    vector     = Column(Text, nullable=False)   # "0.12,0.45,-0.33, ..." (128 values)
    image_path = Column(String, nullable=False)  # path to the saved face image
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="embeddings")


class Attendance(Base):
    """
    The `attendance` table.
    One row = one attendance event (student recognized at a timestamp).
    """
    __tablename__ = "attendance"

    id         = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    timestamp  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    confidence = Column(Float, nullable=False)  # cosine similarity score

    student = relationship("Student", back_populates="attendances")