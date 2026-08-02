# app/services/person_detector.py
# YOLOv8 COCO person detection. Returns person bounding boxes (class 0)
# for CCTV frames — a full-body detector is used because CCTV faces are
# small; the face is later cropped from the person bbox.

from ultralytics import YOLO

model = YOLO("./model/yolov8n.pt")

MIN_DETECTION_CONFIDENCE = 0.5

def detect_persons(frame):
    """Return a list of person bboxes (x1, y1, x2, y2) above confidence."""
    results = model(frame, verbose=False)
    persons = []
    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf < MIN_DETECTION_CONFIDENCE:
                continue
            if int(box.cls[0]) != 0:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            persons.append((x1, y1, x2, y2))
    return persons
