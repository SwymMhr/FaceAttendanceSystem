# app/api/enroll.py
# POST /enroll_student
# Accepts student info + multiple face images.
# Saves images, generates embeddings, stores everything in PostgreSQL.

import os
import uuid
from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
from PIL import Image

from app.db.database import get_db
from app.models.db_models import Student, Embedding
from app.services.model_service import get_embedding, embedding_to_str
from app.core.config import settings

router = APIRouter()


@router.post("/enroll_student")
async def enroll_student(
    student_name: str = Form(...),       # "..." means required
    student_id:   str = Form(...),
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Enroll a new student.

    Form fields:
      - student_name : full name
      - student_id   : unique ID string (e.g. "STU001")
      - images       : one or more face photos (JPEG / PNG)

    Returns the created student record and how many embeddings were saved.
    """

    # ── Guard: don't allow duplicate student_id ───────────────────────────────
    existing = db.query(Student).filter(Student.student_id == student_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Student with ID '{student_id}' is already enrolled."
        )

    # ── Create student row ────────────────────────────────────────────────────
    student = Student(name=student_name, student_id=student_id)
    db.add(student)
    db.flush()   # get the auto-generated student.id without a full commit

    # ── Process each uploaded image ───────────────────────────────────────────
    saved_count = 0

    for upload in images:
        # 1. Read the raw bytes
        raw_bytes = await upload.read()

        # 2. Save the image to disk
        #    We generate a unique filename to avoid collisions.
        ext       = os.path.splitext(upload.filename)[-1] or ".jpg"
        filename  = f"{student_id}_{uuid.uuid4().hex}{ext}"
        save_dir  = os.path.join(settings.UPLOAD_DIR, student_id)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        with open(save_path, "wb") as f:
            f.write(raw_bytes)

        # 3. Generate the 128-dim embedding using your PyTorch model
        from io import BytesIO
        pil_image = Image.open(BytesIO(raw_bytes)).convert("RGB")
        vector    = get_embedding(pil_image)          # numpy [128]
        vec_str   = embedding_to_str(vector)           # "0.12,0.45,..."

        # 4. Store embedding in DB
        emb = Embedding(
            student_id = student.id,
            vector     = vec_str,
            image_path = save_path,
        )
        db.add(emb)
        saved_count += 1

    # ── Commit everything at once ─────────────────────────────────────────────
    db.commit()
    db.refresh(student)

    return {
        "message":        "Student enrolled successfully.",
        "student_db_id":  student.id,
        "student_id":     student.student_id,
        "name":           student.name,
        "embeddings_saved": saved_count,
    }