# app/api/attendance.py
# Three endpoints:
#   POST /recognize_face    — identify who is in a face image
#   POST /mark_attendance   — log an attendance record for a student
#   GET  /get_attendance_logs — fetch all attendance records

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
from app.services.yolo_service import detect_faces
from app.services.crop_utils import crop_with_margin
from app.db.database import get_db
from app.models.db_models import Attendance, Student
from app.services.recognition_service import identify_face

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
        "name":       student.name,
        "student_id": student.student_id,
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

    student = db.query(Student).filter(Student.id == db_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # 🚨 NEW: prevent duplicate attendance within 1 day
    today = datetime.now(timezone.utc) - timedelta(days=1)

    recent = db.query(Attendance).filter(
        and_(
            Attendance.student_id == student.id,
            Attendance.timestamp >= today
        )
    ).first()

    if recent:
        return {
            "message": "Already marked today",
            "student": student.name,
            "status": "skipped"
        }

    record = Attendance(
        student_id=student.id,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Attendance marked.",
        "student": student.name,
        "timestamp": record.timestamp
    }


# ── GET /get_attendance_logs ──────────────────────────────────────────────────

@router.get("/get_attendance_logs")
def get_attendance_logs(
    limit:  int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    """
    Fetch the most recent attendance records (newest first).
    Each record includes the student's name and student_id.
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
            "name":       r.student.name,
            "student_id": r.student.student_id,
            "timestamp":  r.timestamp.isoformat(),
            "confidence": round(r.confidence, 4),
        }
        for r in rows
    ]