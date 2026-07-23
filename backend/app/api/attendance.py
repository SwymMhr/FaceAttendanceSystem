# app/api/attendance.py
#   POST /recognize_face      — identify who is in a face image
#   POST /mark_attendance     — mark attendance via the shared service
#   GET  /get_attendance_logs — fetch recent attendance records
#   POST /finalize_period     — backfill absentees for a finished period (teacher/admin)

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from PIL import Image
from io import BytesIO
from datetime import date as date_type

import cv2
import numpy as np
from app.services.yolo_service import detect_faces
from app.services.crop_utils import crop_with_margin
from app.db.database import get_db
from app.models.db_models import Attendance, Student, Period, User, Batch
from app.services.recognition_service import identify_face
from app.services.attendance_service import mark_attendance_logic
from app.services.absence_service import finalize_period_absentees
from app.api.deps import require_role

router = APIRouter()


# ── POST /recognize_face ──────────────────────────────────────────────────────

@router.post("/recognize_face")
async def recognize_face(
    image: UploadFile = File(...),
    db:    Session    = Depends(get_db),
):
    raw = await image.read()
    pil = Image.open(BytesIO(raw)).convert("RGB")

    frame = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    faces = detect_faces(frame)

    if not faces:
        return {
            "recognized": False,
            "name": "Unknown",
            "student_id": None,
            "confidence": 0.0,
        }

    x1, y1, x2, y2 = max(faces, key=lambda b: (b[2]-b[0]) * (b[3]-b[1]))
    face_crop = crop_with_margin(frame, (x1, y1, x2, y2))
    face_pil  = Image.fromarray(cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB))

    student, score, _ = identify_face(face_pil, db)

    if student is None:
        return {
            "recognized": False,
            "name":       "Unknown",
            "student_id": None,
            "confidence": round(score, 4),
        }

    return {
        "recognized": True,
        "name":       student.student_name,
        "student_id": student.student_code,
        "db_id":      student.id,
        "confidence": round(score, 4),
    }


# ── POST /mark_attendance ─────────────────────────────────────────────────────

@router.post("/mark_attendance")
def mark_attendance(payload: dict, db: Session = Depends(get_db)):
    db_id = payload.get("db_id")
    confidence = payload.get("confidence", 0.0)

    if db_id is None:
        raise HTTPException(status_code=400, detail="db_id is required.")

    result = mark_attendance_logic(db, db_id, confidence)

    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result


# ── GET /get_attendance_logs ──────────────────────────────────────────────────

@router.get("/get_attendance_logs")
def get_attendance_logs(
    start_date:   date_type | None = Query(default=None, description="Include records on/after this date."),
    end_date:     date_type | None = Query(default=None, description="Include records on/before this date."),
    student_name: str | None = Query(default=None, description="Partial, case-insensitive match on student name."),
    batch_id:     int | None = Query(default=None, description="Only records from this batch's periods."),
    teacher_id:   int | None = Query(default=None, description="Only records from periods taught by this teacher."),
    limit:        int = Query(default=100, le=500),
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """
    Fetch attendance records (newest first), optionally filtered by date
    range, student name, batch, and/or teacher. All filters are optional
    and combine with AND — e.g. batch_id + teacher_id together narrows to
    "this batch's classes taught by this teacher".
    """
    query = (
        db.query(Attendance)
          .join(Student, Attendance.student_id == Student.id)
          .join(Period, Attendance.period_id == Period.id)
    )

    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    if student_name:
        query = query.filter(Student.student_name.ilike(f"%{student_name}%"))
    if batch_id:
        query = query.filter(Period.batch_id == batch_id)
    if teacher_id:
        query = query.filter(Period.teacher_id == teacher_id)

    rows = query.order_by(Attendance.timestamp.desc()).limit(limit).all()

    return [
        {
            "id":           r.id,
            "name":         r.student.student_name,
            "student_id":   r.student.student_code,
            "batch_name":   r.period.batch.batch_name if r.period and r.period.batch else None,
            "teacher_name": (r.period.teacher.full_name or r.period.teacher.email) if r.period and r.period.teacher else None,
            "subject":      r.period.subject.subject_name if r.period else None,
            "status":       r.status,
            "date":         r.date.isoformat(),
            "timestamp":    r.timestamp.isoformat(),
            "confidence":   round(r.confidence, 4) if r.confidence is not None else None,
        }
        for r in rows
    ]


# ── GET /attendance_filters ───────────────────────────────────────────────────

@router.get("/attendance_filters")
def get_attendance_filter_options(
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """
    Reference data for the History page's filter dropdowns. Deliberately
    open to teacher + admin (unlike /admin/*, which is admin-only) since
    teachers need these lists to filter attendance history too.
    """
    batches  = db.query(Batch).order_by(Batch.batch_name).all()
    teachers = db.query(User).filter(User.role == "teacher").order_by(User.full_name).all()

    return {
        "batches":  [{"id": b.id, "batch_name": b.batch_name} for b in batches],
        "teachers": [{"id": t.id, "name": t.full_name or t.email} for t in teachers],
    }


# ── POST /finalize_period ─────────────────────────────────────────────────────

@router.post("/finalize_period")
def finalize_period(
    period_id: int,
    target_date: date_type | None = None,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """
    Manually trigger absence backfill + emails for one period. Normally
    the background scheduler does this automatically once a period ends
    (see app/services/scheduler.py), but a teacher/admin can also trigger
    it on demand — e.g. right after class instead of waiting for the
    next scheduler tick.
    """
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found.")

    if current_user.role == "teacher" and period.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only finalize your own periods.")

    try:
        return finalize_period_absentees(db, period_id, target_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))