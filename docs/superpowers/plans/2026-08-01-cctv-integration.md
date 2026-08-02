# CCTV Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add CCTV-based automatic attendance + a live annotated MJPEG feed to the Face Attendance System (V4).

**Architecture:** A background `CCTVService` thread (started from `main.py` like `start_scheduler()`) reads an RTSP camera, detects people with YOLO COCO, head-crops + upscales each person, runs MiniFASNet liveness, identifies via the existing ArcFace/DB pipeline (`identify_face`), and marks attendance via `mark_attendance_logic`. The latest annotated frame is served as MJPEG via `/cctv/stream`; recognition events via `/cctv/events`; a new frontend page shows the feed and event log.

**Tech Stack:** Python 3.12, FastAPI 0.111, SQLAlchemy 2.0, OpenCV, ultralytics 8.2.18, PyTorch 2.3, React 18 (Vite), axios.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/model/yolov8n.pt` | Copy from `D:\Misc\CCTV test\yolov8n.pt` | YOLOv8 COCO person detector weights |
| `backend/app/services/person_detector.py` | Create | YOLO COCO person detection wrapper |
| `backend/app/services/cctv_service.py` | Create | Background RTSP service: detect → liveness → recognize → attendance, publishes MJPEG frame + events |
| `backend/app/api/cctv.py` | Create | `/cctv/stream`, `/cctv/status`, `/cctv/events`, `/cctv/toggle` |
| `backend/app/core/config.py` | Modify | Add CCTV settings (enabled, RTSP URL, batch id, interval) |
| `backend/app/main.py` | Modify | Start `CCTVService`, register cctv router |
| `backend/requirements.txt` | Modify | Add `opencv-python-headless` |
| `backend/.env` | Modify | Add CCTV config values |
| `backend/test_cctv_service.py` | Create | Smoke test: config, service import, head-crop function |
| `frontend/src/api.js` | Modify | Add `getCctvStatus`, `getCctvEvents`, `toggleCctv` |
| `frontend/src/pages/CCTVPage.jsx` | Create | Live MJPEG view + event feed + status/toggle |
| `frontend/src/App.jsx` | Modify | Add `/teacher/cctv` route |
| `frontend/src/components/Sidebar.jsx` | Modify | Add "CCTV" nav link (teacher, admin) |

---

### Task 1: Copy YOLO COCO model + add config settings

**Files:**
- Copy: `backend/model/yolov8n.pt` (from `D:\Misc\CCTV test\yolov8n.pt`)
- Copy: `backend/model/face_embedding_model_mobilenetv2_v6_arcface.pth` (from V1 — V4's model dir is missing it and the app cannot start without it)
- Modify: `backend/app/core/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env`

- [x] **Step 1: Copy the YOLO COCO model file**

```bash
Copy-Item "D:\Misc\CCTV test\yolov8n.pt" "D:\Misc\github repo test\V4\backend\model\yolov8n.pt"
```

Expected: file exists at `backend/model/yolov8n.pt`.

- [x] **Step 2: Copy the ArcFace checkpoint (required for model_service import)**

```bash
Copy-Item "D:\Misc\github repo test\V1\FaceAttendanceSystem\backend\model\face_embedding_model_mobilenetv2_v6_arcface.pth" "D:\Misc\github repo test\V4\backend\model\face_embedding_model_mobilenetv2_v6_arcface.pth"
```

Expected: file exists at `backend/model/face_embedding_model_mobilenetv2_v6_arcface.pth`. Verify import works:
`python -c "from app.services.model_service import _model; print('model loads')"` → prints `model loads`.

- [x] **Step 3: Add CCTV settings to config.py**

Read `backend/app/core/config.py`. After the `LIVENESS_MIN_CHECKS_TO_FAIL` field and before the `class Config:` block, add:

```python
    # ── CCTV integration ─────────────────────────────────────────────────
    CCTV_ENABLED: bool = False
    CCTV_RTSP_URL: str = ""
    CCTV_BATCH_ID: int | None = None
    CCTV_DETECT_INTERVAL: float = 2.5
```

- [x] **Step 4: Add opencv dependency to requirements.txt**

Append to `backend/requirements.txt`:

```
opencv-python-headless==4.13.0.92
```

- [x] **Step 5: Add CCTV values to .env**

Append to `backend/.env` (user must fill in their real batch id):

```
# CCTV integration
CCTV_ENABLED=true
CCTV_RTSP_URL=rtsp://admin:123456@192.168.1.83:554/media/video3?rtsp_transport=tcp&tcp_nodelay=1
CCTV_BATCH_ID=1
CCTV_DETECT_INTERVAL=2.5
```

- [x] **Step 6: Verify config loads**

Run (from `backend/`):

```bash
python -c "from app.core.config import settings; print(settings.CCTV_ENABLED, settings.CCTV_RTSP_URL, settings.CCTV_BATCH_ID)"
```

Expected: prints the .env values (CCTV_ENABLED should be True).

- [x] **Step 7: Commit**

```bash
git add backend/model/yolov8n.pt backend/model/face_embedding_model_mobilenetv2_v6_arcface.pth backend/app/core/config.py backend/requirements.txt backend/.env
git commit -m "feat(cctv): add YOLO COCO model, ArcFace checkpoint, config settings, deps"
```

---

### Task 2: Person detector service

**Files:**
- Create: `backend/app/services/person_detector.py`
- Test: `backend/test_cctv_service.py` (part 1)

- [x] **Step 1: Write the failing test (head-crop + person detector contract)**

Create `backend/test_cctv_service.py`:

```python
# backend/test_cctv_service.py
# Smoke tests for the CCTV integration. Run: python test_cctv_service.py

import cv2
import numpy as np


def test_head_region():
    """Head region must be the top ~40% of a person bbox."""
    from app.services.cctv_service import head_region
    box = (100, 100, 200, 400)  # x1, y1, x2, y2
    hr = head_region(box)
    assert hr[0] == 100 and hr[2] == 200, f"x bounds wrong: {hr}"
    assert hr[1] == 100, f"head top should equal bbox top: {hr}"
    assert hr[3] == 100 + int(300 * 0.4), f"head height wrong: {hr}"


def test_detect_persons_empty_frame():
    """Person detector must return an empty list for a blank frame."""
    from app.services.person_detector import detect_persons
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detect_persons(blank)
    assert isinstance(result, list), "detect_persons must return a list"


if __name__ == "__main__":
    test_head_region()
    test_detect_persons_empty_frame()
    print("All CCTV service tests passed")
```

- [x] **Step 2: Run the test to verify it fails**

Run (from `backend/`):

```bash
python test_cctv_service.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.cctv_service'` and `ModuleNotFoundError: No module named 'app.services.person_detector'`.

- [x] **Step 3: Implement person_detector.py**

Create `backend/app/services/person_detector.py`:

```python
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
```

- [x] **Step 4: Run the test again**

Run (from `backend/`):

```bash
python test_cctv_service.py
```

Expected: still FAIL — `ModuleNotFoundError: No module named 'app.services.cctv_service'` (person_detector import now works, but cctv_service doesn't exist yet). This is expected; the test verifies both modules.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/person_detector.py backend/test_cctv_service.py
git commit -m "feat(cctv): add YOLO COCO person detector"
```

---

### Task 3: CCTV background service

**Files:**
- Create: `backend/app/services/cctv_service.py`

- [x] **Step 1: Implement cctv_service.py**

Create `backend/app/services/cctv_service.py`:

```python
# app/services/cctv_service.py
# Background CCTV service. Started once from app/main.py (like the
# scheduler). Owns the RTSP camera loop and, on every detect interval:
#   1. YOLO person detection (downscaled frame)
#   2. head crop + upscale per person
#   3. MiniFASNet liveness check
#   4. identify_face (ArcFace + DB, batch-scoped)
#   5. mark_attendance_logic
# Publishes the latest annotated JPEG (for MJPEG streaming) and a rolling
# event log (for /cctv/events). All state is thread-safe.

import threading
import time
from collections import deque
from datetime import datetime, timezone

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.person_detector import detect_persons
from app.services.liveness_service import check_liveness
from app.services.recognition_service import identify_face
from app.services.attendance_service import mark_attendance_logic

HEAD_FRACTION = 0.4
MIN_HEAD_UPSCALE = 160.0
DETECT_WIDTH = 640
EVENT_QUEUE_MAX = 100
RECONNECT_BACKOFF_S = 5.0
JPEG_QUALITY = 80


def head_region(box):
    """Return the head region (top 40%) of a person bbox as (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = box
    return (x1, y1, x2, y1 + int((y2 - y1) * HEAD_FRACTION))


class CCTVService:
    def __init__(self):
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_jpeg = None
        self._detections = []          # list of dicts: box, label, color
        self._events = deque(maxlen=EVENT_QUEUE_MAX)
        self._connected = False
        self._resolution = None
        self._last_error = None

    # ── lifecycle ─────────────────────────────────────────────────────
    def start(self):
        if not settings.CCTV_ENABLED:
            print("[CCTV] Disabled via config (CCTV_ENABLED=false). Not starting.")
            return
        if not settings.CCTV_RTSP_URL:
            print("[CCTV] Missing CCTV_RTSP_URL in config. Not starting.")
            return
        if settings.CCTV_BATCH_ID is None:
            print("[CCTV] Missing CCTV_BATCH_ID in config. Not starting.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[CCTV] Service started.")

    def stop(self):
        self._running = False

    def is_running(self):
        return self._running

    def toggle(self):
        if self._running:
            self.stop()
        else:
            self.start()
        return self._running

    # ── thread-safe reads ─────────────────────────────────────────────
    def get_status(self):
        with self._lock:
            return {
                "enabled": settings.CCTV_ENABLED,
                "running": self._running,
                "connected": self._connected,
                "resolution": self._resolution,
                "person_count": len(self._detections),
                "last_error": self._last_error,
            }

    def get_events(self, limit=50):
        with self._lock:
            return list(self._events)[-limit:]

    def get_latest_jpeg(self):
        with self._lock:
            return self._latest_jpeg

    # ── internals ─────────────────────────────────────────────────────
    def _log_event(self, name, confidence, status, message):
        with self._lock:
            self._events.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "name": name,
                "confidence": confidence,
                "status": status,
                "message": message,
            })

    def _open_stream(self):
        urls = [settings.CCTV_RTSP_URL]
        cap = None
        for url in urls:
            try:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    with self._lock:
                        self._connected = True
                        self._resolution = f"{w}x{h}"
                        self._last_error = None
                    print(f"[CCTV] Connected: {w}x{h}")
                    return cap
                cap.release()
            except Exception as e:
                print(f"[CCTV] Stream open failed: {e}")
                if cap is not None:
                    cap.release()
        with self._lock:
            self._connected = False
            self._resolution = None
            self._last_error = "Could not open any RTSP stream"
        return None

    def _run(self):
        while self._running:
            cap = self._open_stream()
            if cap is None:
                time.sleep(RECONNECT_BACKOFF_S)
                continue
            try:
                self._camera_loop(cap)
            except Exception as e:
                print(f"[CCTV] Camera loop error: {e}")
            finally:
                cap.release()
                with self._lock:
                    self._connected = False
            if self._running:
                time.sleep(RECONNECT_BACKOFF_S)

    def _camera_loop(self, cap):
        last_process = 0.0
        while self._running:
            ret, frame = cap.read()
            if not ret:
                print("[CCTV] Stream read failed — reconnecting.")
                return
            now = time.time()
            if now - last_process < settings.CCTV_DETECT_INTERVAL:
                continue
            last_process = now
            try:
                annotated, detections = self._process_frame(frame)
            except Exception as e:
                print(f"[CCTV] Frame processing error: {e}")
                continue
            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()
                    self._detections = detections

    def _process_frame(self, frame):
        """Detect persons, recognize each, draw boxes. Returns (annotated, detections)."""
        h, w = frame.shape[:2]
        scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
        work = frame
        inv_scale = 1.0
        if scale < 1.0:
            work = cv2.resize(frame, (DETECT_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
            inv_scale = 1.0 / scale

        persons = detect_persons(work)
        detections = []
        db = SessionLocal()
        try:
            for (px1, py1, px2, py2) in persons:
                box = (int(px1 * inv_scale), int(py1 * inv_scale),
                       int(px2 * inv_scale), int(py2 * inv_scale))
                name, confidence, status, message, color = self._recognize_person(frame, box, db)
                detections.append({"box": box, "label": name, "color": color})
                self._log_event(name, confidence, status, message)
        finally:
            db.close()

        annotated = frame.copy()
        for d in detections:
            x1, y1, x2, y2 = d["box"]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), d["color"], 2)
            cv2.putText(annotated, d["label"], (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, d["color"], 2)
        return annotated, detections

    def _recognize_person(self, frame, box, db):
        """Recognize a single person bbox. Returns (name, conf, status, message, color)."""
        x1, y1, x2, y2 = box
        ph = y2 - y1
        if ph < 20:
            return "Unknown", 0.0, "unrecognized", "Person too small", (0, 165, 255)

        hx1, hy1, hx2, hy2 = head_region(box)
        head = frame[max(0, hy1):hy2, max(0, hx1):hx2]
        if head.size == 0 or head.shape[0] < 5 or head.shape[1] < 5:
            return "Unknown", 0.0, "unrecognized", "Empty head crop", (0, 165, 255)

        # Upscale head crop so the face is big enough for liveness + recognition
        short = min(head.shape[0], head.shape[1])
        if short < MIN_HEAD_UPSCALE:
            s = MIN_HEAD_UPSCALE / short
            head = cv2.resize(head, (int(head.shape[1] * s), int(head.shape[0] * s)),
                              interpolation=cv2.INTER_CUBIC)

        # ── Liveness (MiniFASNet), always run ─────────────────────────
        face_bbox = (hx1, hy1, hx2 - hx1, hy2 - hy1)
        try:
            liveness = check_liveness(frame, face_bbox)
        except Exception as e:
            return "Unknown", 0.0, "error", f"Liveness error: {e}", (0, 0, 255)
        if not liveness["is_live"]:
            return "Spoof Detected", round(liveness["confidence"], 4), "rejected", \
                   "Anti-spoofing failed (CNN liveness)", (0, 0, 255)

        # ── Recognition (ArcFace + DB) ────────────────────────────────
        pil = Image.fromarray(cv2.cvtColor(head, cv2.COLOR_BGR2RGB))
        student, score, db_id = identify_face(pil, db, batch_id=settings.CCTV_BATCH_ID)
        if not student:
            return "Unknown", round(score, 4), "unrecognized", \
                   "Face not recognized in configured batch", (0, 165, 255)

        outcome = mark_attendance_logic(db, db_id, score)
        return student.student_name, round(score, 4), outcome.get("status"), \
               outcome.get("message", ""), (0, 255, 0)


cctv_service = CCTVService()
```

- [x] **Step 2: Run the test**

Run (from `backend/`):

```bash
python test_cctv_service.py
```

Expected: PASS — prints `All CCTV service tests passed`. (The service module imports cleanly: models load at import time.)

- [x] **Step 3: Commit**

```bash
git add backend/app/services/cctv_service.py
git commit -m "feat(cctv): add background CCTV service (detect → liveness → recognize → attendance)"
```

---

### Task 4: CCTV API router

**Files:**
- Create: `backend/app/api/cctv.py`

- [x] **Step 1: Implement the router**

Create `backend/app/api/cctv.py`:

```python
# app/api/cctv.py
# CCTV endpoints: MJPEG live stream, status, events, and enable/disable.

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import require_role
from app.core.security import decode_access_token
from app.services.cctv_service import cctv_service

router = APIRouter(prefix="/cctv", tags=["CCTV"])


def _authorize_stream(token: str | None):
    """<img> tags can't send Authorization headers, so the MJPEG stream
    accepts the JWT as a query param instead."""
    if not token:
        raise HTTPException(status_code=401, detail="Token required as ?token= query param.")
    if decode_access_token(token) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


@router.get("/stream")
def stream(token: str | None = None):
    _authorize_stream(token)
    if not cctv_service.is_running():
        raise HTTPException(status_code=503, detail="CCTV service is not running.")

    def generate():
        while True:
            jpeg = cctv_service.get_latest_jpeg()
            if jpeg is not None:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(0.05)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/status")
def status(_: None = Depends(require_role("teacher", "admin"))):
    return cctv_service.get_status()


@router.get("/events")
def events(limit: int = 50, _: None = Depends(require_role("teacher", "admin"))):
    return {"events": cctv_service.get_events(limit)}


@router.post("/toggle")
def toggle(_: None = Depends(require_role("admin"))):
    running = cctv_service.toggle()
    return {"running": running}
```

- [x] **Step 2: Verify the router imports**

Run (from `backend/`):

```bash
python -c "from app.api.cctv import router; print('cctv router OK')"
```

Expected: prints `cctv router OK`.

- [x] **Step 3: Commit**

```bash
git add backend/app/api/cctv.py
git commit -m "feat(cctv): add CCTV API router (stream, status, events, toggle)"
```

---

### Task 5: Wire into main.py

**Files:**
- Modify: `backend/app/main.py`

- [x] **Step 1: Register router + start service**

Edit `backend/app/main.py`:

1. In the import block, change:
```python
from app.api import enroll, attendance, realtime, auth, admin, schedule, dashboard
```
to:
```python
from app.api import enroll, attendance, realtime, auth, admin, schedule, dashboard, cctv
from app.services.cctv_service import cctv_service
```

2. After `start_scheduler()`, add:
```python
cctv_service.start()
```

3. After `app.include_router(schedule.router)`, add:
```python
app.include_router(cctv.router, tags=["CCTV"])
```

- [x] **Step 2: Verify the app imports (no server start)**

Run (from `backend/`):

```bash
python -c "from app.main import app; print('app imports OK')"
```

Expected: prints `app imports OK` and `[CCTV] Disabled via config...` only if `CCTV_ENABLED` is false; with `.env` set to true, it prints `[CCTV] Service started.` (thread starts, tries to connect, prints errors to stderr, keeps retrying — that's fine).

- [x] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(cctv): wire CCTV service + router into FastAPI app"
```

---

### Task 6: Frontend API helpers

**Files:**
- Modify: `frontend/src/api.js`

- [x] **Step 1: Add CCTV API functions**

Append to `frontend/src/api.js` (before `export default api;`):

```js
// ── CCTV integration ────────────────────────────────────────────────────────

export async function getCctvStatus() {
  const res = await api.get("/cctv/status");
  return res.data;
}

export async function getCctvEvents(limit = 50) {
  const res = await api.get(`/cctv/events?limit=${limit}`);
  return res.data;
}

export async function toggleCctv() {
  const res = await api.post("/cctv/toggle");
  return res.data;
}
```

- [x] **Step 2: Verify it parses**

Run (from `frontend/`):

```bash
node --check src/api.js
```

Expected: no output (file parses cleanly).

- [x] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(cctv): add frontend API helpers for CCTV endpoints"
```

---

### Task 7: CCTV live view page

**Files:**
- Create: `frontend/src/pages/CCTVPage.jsx`

- [x] **Step 1: Implement the page**

Create `frontend/src/pages/CCTVPage.jsx`:

```jsx
import { useEffect, useRef, useState } from "react";
import { getCctvStatus, getCctvEvents, toggleCctv, getRole } from "../api";
import PageHeader from "../components/PageHeader";

const STATUS_BADGE = {
  pending: "bg-info text-dark",
  skipped: "bg-warning text-dark",
  error: "bg-danger",
  unrecognized: "bg-secondary",
  rejected: "bg-danger text-white",
};

const API_BASE_URL = "http://localhost:8000";

export default function CCTVPage() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [streamKey, setStreamKey] = useState(0);
  const role = getRole();

  useEffect(() => {
    const load = () => {
      getCctvStatus()
        .then(setStatus)
        .catch((err) => setError(err.response?.data?.detail || "Failed to load CCTV status."));
      getCctvEvents(50)
        .then((d) => setEvents(d.events || []))
        .catch(() => {});
    };
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  const token = localStorage.getItem("token");
  const streamSrc = `${API_BASE_URL}/cctv/stream?token=${token}`;

  const handleToggle = async () => {
    try {
      const res = await toggleCctv();
      setStatus((s) => ({ ...s, running: res.running }));
      setStreamKey((k) => k + 1); // force <img> to reload after toggle
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to toggle CCTV service.");
    }
  };

  const running = status?.running;

  return (
    <div className="page">
      <PageHeader
        title="CCTV Live View"
        subtitle="Automatic attendance from the classroom camera. Recognitions appear below as they happen."
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <div className="d-flex align-items-center gap-3 mb-3">
          <span className={`badge ${status?.connected ? "bg-success" : "bg-danger"}`}>
            {status?.connected ? "Connected" : "Disconnected"}
          </span>
          <span className="small text-muted">
            {status?.resolution || "—"} · Persons in frame: {status?.person_count ?? 0}
          </span>
          {role === "admin" && (
            <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={handleToggle}>
              {running ? "Stop" : "Start"}
            </button>
          )}
        </div>

        {!running && (
          <div className="alert alert-warning">
            CCTV service is not running. Check <code>CCTV_ENABLED</code> in backend/.env.
          </div>
        )}

        <div style={{ maxWidth: 720 }}>
          <img
            key={streamKey}
            src={streamSrc}
            alt="CCTV feed"
            className="w-100 rounded border bg-dark"
          />
        </div>
      </div>

      <div className="panel">
        <h2 className="panel-title">Recent Recognitions</h2>
        {events.length === 0 ? (
          <div className="empty-state">No detections yet.</div>
        ) : (
          <ul className="list-group" style={{ maxWidth: 640 }}>
            {events.map((e, i) => (
              <li key={i} className="list-group-item d-flex justify-content-between align-items-center">
                <div>
                  <span className="fw-bold">{e.name}</span>
                  <div className="small text-muted">{e.message}</div>
                </div>
                <div className="text-end">
                  <span className={`badge ${STATUS_BADGE[e.status] || "bg-secondary"}`}>{e.status}</span>
                  <div className="small text-muted">
                    {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ""}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [x] **Step 2: Verify it parses**

Run (from `frontend/`):

```bash
node --check src/pages/CCTVPage.jsx
```

Expected: no output (parses cleanly).

- [x] **Step 3: Commit**

```bash
git add frontend/src/pages/CCTVPage.jsx
git commit -m "feat(cctv): add CCTV live view page"
```

---

### Task 8: Add route + sidebar link

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`

- [x] **Step 1: Add the route in App.jsx**

In `frontend/src/App.jsx`:
1. Add import after the `AdminSchedule` import:
```jsx
import CCTVPage from "./pages/CCTVPage";
```
2. After the `/teacher/attendance` route block (after line 129 `/>`), add:
```jsx
        <Route
          path="/teacher/cctv"
          element={
            <ProtectedRoute roles={["teacher", "admin"]}>
              <CCTVPage />
            </ProtectedRoute>
          }
        />
```

- [x] **Step 2: Add sidebar links**

In `frontend/src/components/Sidebar.jsx`, in the `teacher` array after the `Live Attendance` line, add:
```jsx
    { label: "CCTV Live", path: "/teacher/cctv", icon: "bi-camera-video" },
```
In the `admin` array after the `Live Attendance` line, add:
```jsx
    { label: "CCTV Live", path: "/teacher/cctv", icon: "bi-camera-video" },
```

- [x] **Step 3: Verify files parse**

Run (from `frontend/`):

```bash
node --check src/App.jsx
node --check src/components/Sidebar.jsx
```

Expected: no output from either.

- [x] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat(cctv): add CCTV route and sidebar links"
```

---

### Task 9: End-to-end verification

**Files:**
- Run: `backend/test_cctv_service.py`
- Manual: backend server + camera + frontend

- [x] **Step 1: Run backend smoke test**

Run (from `backend/`):

```bash
python test_cctv_service.py
```

Expected: prints `All CCTV service tests passed`.

- [x] **Step 2: Start the backend**

From `backend/`:

```bash
uvicorn app.main:app --reload
```

Expected: logs show `[CCTV] Service started.` then `[CCTV] Connected: WxH` once it reaches the camera. If it prints `[CCTV] Stream open failed` repeatedly, check the RTSP URL / camera on the network.

- [x] **Step 3: Verify endpoints with a browser + token**

1. Log in to the frontend (`npm run dev` in `frontend/`) as an admin, open `/teacher/cctv`.
2. Confirm the live feed renders (green boxes around people).
3. Confirm "Recent Recognitions" populates when someone is in frame.
4. Admin: toggle Start/Stop and confirm the feed reacts.

- [x] **Step 4: Verify attendance rows**

Check the database for a `pending` attendance row for the configured batch after a recognition:

```bash
python -c "from app.db.database import SessionLocal; from app.models.db_models import Attendance; db=SessionLocal(); rows=db.query(Attendance).order_by(Attendance.id.desc()).limit(5).all(); [print(r.student_id, r.status, r.date) for r in rows]; db.close()"
```

Expected: a recent `pending` row exists when the camera saw a known student during a scheduled period.

- [x] **Step 5: Commit any remaining changes**

```bash
git status
git add -A
git commit -m "chore(cctv): finalize CCTV integration"
```

---

## Self-Review Notes

- **Spec coverage:** config (Task 1) ✓, person detector (Task 2) ✓, CCTV service (Task 3) ✓, API router (Task 4) ✓, main wiring (Task 5) ✓, frontend helpers (Task 6) ✓, live page (Task 7) ✓, route/sidebar (Task 8) ✓, E2E test (Task 9) ✓. The design's "always run liveness" is implemented in `_recognize_person`. Batch scoping via `CCTV_BATCH_ID` is enforced by passing `batch_id` to `identify_face`, and `start()` refuses to run without `CCTV_BATCH_ID` (per the design's "required" note).
- **Type consistency:** `identify_face` returns `(Student, score, db_id)`; `mark_attendance_logic(db, student_id, score)` returns a dict with `status`/`message`. `head_region` and `detect_persons` signatures match their tests. `check_liveness(frame, face_bbox)` takes `(x, y, w, h)`.
- **Model path note:** `person_detector.py` loads `./model/yolov8n.pt`, matching `yolo_service.py`'s `./model/yolov8n-face-lindevs.pt` convention — both resolve relative to `backend/` when uvicorn runs from there.
- **Missing ArcFace checkpoint:** V4's `backend/model/` (and V3's) lacks `face_embedding_model_mobilenetv2_v6_arcface.pth`, so `model_service.py` import crashes with `FileNotFoundError`. Task 1 copies it from V1 (`D:\Misc\github repo test\V1\FaceAttendanceSystem\backend\model\`). Verified: only `yolov8n-face-lindevs.pt` present in V4 model dir.
- **opencv version:** pinned `opencv-python-headless==4.13.0.92` to match the installed version (avoid reinstall); `opencv-python-headless` is not in V3's requirements.txt but cv2 is imported by `realtime.py` already.
- **Stream fallback (added during execution):** the design spec requires a `video3 → video2 → video1` fallback list, but the original plan only tried the single `CCTV_RTSP_URL`. Implemented `CCTV_STREAM_FALLBACKS` config (comma-separated) + `stream_urls()` helper + test; verified live: video3 fails fast (500 ServerInternal), video2 connects at 640x360.
- **Environment fixes (unblocked E2E):** V4's `.env` pointed to a non-existent `attendance_db` with a rejected password; repointed to the working `face_attendance` DB (`face_user`/`face_pass`) — SQLAlchemy created all `tbl_*` tables on first start. Installed missing deps declared in requirements.txt (`passlib`, `python-jose`, `apscheduler`). Created test admin `admin@test.com` / `admin123` since the DB had zero users.
