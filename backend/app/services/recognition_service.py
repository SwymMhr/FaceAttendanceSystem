# app/services/recognition_service.py
# Contains the face-recognition business logic:
#   - Given a face image, find the best matching student in the database.
#   - Returns the matched student (or None) and the confidence score.

import numpy as np
from sqlalchemy.orm import Session

from app.models.db_models import Embedding, Student
from app.services.model_service import (
    get_embedding,
    str_to_embedding,
    cosine_similarity,
    VERIFICATION_THRESHOLD,
)
from PIL import Image


def identify_face(pil_image: Image.Image, db: Session):
    """
    Given a cropped face image:
      1. Compute its embedding.
      2. Compare against every stored embedding in the database.
      3. Return (Student | None, best_score, student_id_int | None).

    If the best score is below VERIFICATION_THRESHOLD (computed during
    training, not a hand-picked guess), the face is 'Unknown'.
    """
    # Step 1 — compute embedding for the incoming face
    query_vec = get_embedding(pil_image)

    # Step 2 — load all stored embeddings from DB
    all_embeddings = db.query(Embedding).all()

    if not all_embeddings:
        return None, 0.0, None

    # Step 3 — find the best match
    best_score   = -1.0
    best_student = None
    best_student_db_id = None

    for emb_row in all_embeddings:
        stored_vec = str_to_embedding(emb_row.vector)
        score = cosine_similarity(query_vec, stored_vec)

        if score > best_score:
            best_score         = score
            best_student_db_id = emb_row.student_id
            best_student       = emb_row.student

    # Step 4 — apply threshold
    if best_score < VERIFICATION_THRESHOLD:
        return None, best_score, None

    # Step 5 — fetch the Student row
    student = db.query(Student).filter(Student.id == best_student_db_id).first()
    return student, best_score, best_student_db_id