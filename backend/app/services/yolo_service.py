from ultralytics import YOLO

model = YOLO("./model/yolov8n-face-lindevs.pt")

MIN_DETECTION_CONFIDENCE = 0.6

def detect_faces(frame):
    results = model(frame, verbose=False)
    faces = []
    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf < MIN_DETECTION_CONFIDENCE:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            faces.append((x1, y1, x2, y2))
    return faces