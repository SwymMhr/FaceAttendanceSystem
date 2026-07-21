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
from app.models.db_models import Attendance, Student, Period, User
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
    limit:  int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    """
    Fetch the most recent attendance records (newest first), including
    which subject/period each one was for.
    """
    rows = (
        db.query(Attendance)
          .join(Student)
          .order_by(Attendance.timestamp.desc())
          .limit(limit)
          .all()
    )

    return [
        {
            "id":         r.id,
            "name":       r.student.student_name,
            "student_id": r.student.student_code,
            "subject":    r.period.subject.subject_name if r.period else None,
            "status":     r.status,
            "date":       r.date.isoformat(),
            "timestamp":  r.timestamp.isoformat(),
            "confidence": round(r.confidence, 4) if r.confidence is not None else None,
        }
        for r in rows
    ]


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