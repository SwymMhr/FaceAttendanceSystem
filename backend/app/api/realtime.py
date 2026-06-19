from fastapi import APIRouter, File, UploadFile, Depends
from sqlalchemy.orm import Session
import numpy as np
import cv2
from PIL import Image
from io import BytesIO

from app.db.database import get_db
from app.services.yolo_service import detect_faces
from app.services.recognition_service import identify_face
from app.services.attendance_service import mark_attendance_logic

router = APIRouter()

@router.post("/process_frame")
async def process_frame(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    # Read frame
    contents = await image.read()
    npimg = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    # Detect faces
    faces = detect_faces(frame)

    results = []

    for (x1, y1, x2, y2) in faces:

        face_crop = frame[y1:y2, x1:x2]

        pil_img = Image.fromarray(
            cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        )

        student, score, db_id = identify_face(pil_img, db)

        if student:
            mark_attendance_logic(db, db_id, score)

            results.append({
                "name": student.name,
                "confidence": score
            })

    return {"results": results}