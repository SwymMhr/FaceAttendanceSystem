from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
from app.services.crop_utils import crop_with_margin

from app.db.database import get_db
from app.models.db_models import Batch
from app.services.yolo_service import detect_faces
from app.services.recognition_service import identify_face
from app.services.attendance_service import mark_attendance_logic

router = APIRouter()

@router.post("/process_frame")
async def process_frame(
    image: UploadFile = File(...),
    batch_id: int = Form(..., description="Only students in this batch are searched/matched."),
    db: Session = Depends(get_db)
):
    if not db.query(Batch).filter(Batch.id == batch_id).first():
        raise HTTPException(status_code=404, detail="Batch not found.")

    # Read frame
    contents = await image.read()
    npimg = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    # Detect faces
    faces = detect_faces(frame)

    results = []

    for (x1, y1, x2, y2) in faces:

        face_crop = crop_with_margin(frame, (x1, y1, x2, y2))

        pil_img = Image.fromarray(
            cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        )

        student, score, db_id = identify_face(pil_img, db, batch_id=batch_id)

        if not student:
            # A face was detected in the frame, but it didn't match anyone
            # closely enough in this batch (or there are no enrolled
            # embeddings for this batch at all).
            results.append({
                "name": "Unknown",
                "confidence": round(score, 4),
                "attendance_status": "unrecognized",
                "message": "Face detected but not recognized as any student enrolled in this batch.",
            })
            continue

        # mark_attendance_logic() returns a real status ("marked" / "skipped"
        # / "error") with a human-readable reason — surface it instead of
        # silently discarding it like the old version did. A recognized face
        # does NOT guarantee attendance was actually written (e.g. no class
        # currently in session for that student's batch).
        outcome = mark_attendance_logic(db, db_id, score)

        results.append({
            "name": student.student_name,
            "confidence": round(score, 4),
            "attendance_status": outcome.get("status"),
            "message": outcome.get("message"),
            "subject": outcome.get("subject"),
        })

    return {"results": results}