# app/api/enroll.py
# GET  /students/{student_id}/embeddings — how many face photos are registered
# POST /register_face                    — add face photo(s) for an EXISTING student
#
# Students are created by an admin via /admin/users/students (see admin.py).
# This router only ever attaches embeddings to a student that already exists —
# it never creates one. That keeps "who's a valid login" (admin's job) and
# "what does their face look like" (this router's job) as separate concerns.

import os
import uuid
from io import BytesIO

from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
from PIL import Image

import cv2
import numpy as np
from app.services.yolo_service import detect_faces
from app.services.crop_utils import crop_with_margin

from app.db.database import get_db
from app.models.db_models import Student, Embedding
from app.services.model_service import get_embedding, embedding_to_str
from app.core.config import settings
from app.api.deps import require_role

router = APIRouter()


# ── GET /students/{student_id}/embeddings ──────────────────────────────────

@router.get("/students/{student_id}/embeddings")
def get_embedding_count(
    student_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("teacher", "admin")),
):
    """How many face photos are currently registered for this student —
    used by the registration UI to show 'already has N photos' before
    adding more."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    count = db.query(Embedding).filter(Embedding.student_id == student_id).count()
    return {"student_id": student_id, "embeddings_count": count}


# ── POST /register_face ─────────────────────────────────────────────────────

@router.post("/register_face")
async def register_face(
    student_id: int = Form(...),         # existing tbl_students.id — NOT student_code
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("teacher", "admin")),
):
    """
    Add one or more face photos for an already-existing student, generating
    and storing an embedding for each usable photo.

    Form fields:
      - student_id : the student's database id (from the admin-created roster)
      - images     : one or more face photos (JPEG / PNG)

    Photos where no face is detected are skipped rather than rejected
    outright, so a bad photo in a multi-upload doesn't fail the whole batch.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    saved_count = 0
    skipped_count = 0

    for upload in images:
        raw_bytes = await upload.read()

        ext      = os.path.splitext(upload.filename)[-1] or ".jpg"
        filename = f"{student.student_code}_{uuid.uuid4().hex}{ext}"
        save_dir = os.path.join(settings.UPLOAD_DIR, student.student_code)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        pil_image = Image.open(BytesIO(raw_bytes)).convert("RGB")
        frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        faces = detect_faces(frame)

        if not faces:
            skipped_count += 1
            continue  # no face found in this photo — skip it, don't poison the gallery

        # Largest box if multiple faces were picked up in the frame.
        x1, y1, x2, y2 = max(faces, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        face_crop = crop_with_margin(frame, (x1, y1, x2, y2))
        face_pil = Image.fromarray(cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB))

        vector = get_embedding(face_pil)
        vec_str = embedding_to_str(vector)

        with open(save_path, "wb") as f:
            f.write(raw_bytes)

        emb = Embedding(
            student_id=student.id,
            vector=vec_str,
            image_path=save_path,
        )
        db.add(emb)
        saved_count += 1

    db.commit()

    total_embeddings = db.query(Embedding).filter(Embedding.student_id == student.id).count()

    return {
        "message":            "Face registration complete.",
        "student_db_id":      student.id,
        "student_code":       student.student_code,
        "student_name":       student.student_name,
        "images_registered":  saved_count,
        "images_skipped_no_face": skipped_count,
        "total_embeddings":   total_embeddings,
    }