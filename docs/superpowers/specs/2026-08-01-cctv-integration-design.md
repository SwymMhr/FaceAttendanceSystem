# CCTV Integration Design — V4

Date: 2026-08-01

Status: Approved (2026-08-01)

## Goal

Add CCTV-based automatic attendance + live annotated feed to the Face
Attendance System. V4 is a new version of the project (copy of V3) with
CCTV integrated. A background service in the FastAPI backend connects to
a classroom RTSP camera, continuously detects people, recognizes enrolled
students, marks attendance through the existing DB/attendance pipeline, and
serves an annotated MJPEG live view + event feed to the web frontend.

## Requirements

- Auto-attendance: students detected by the classroom CCTV camera get marked
  "pending" (awaiting teacher confirmation) through the existing
  `mark_attendance_logic` — the same as webcam detections.
- Live view: a new dedicated frontend page shows the annotated CCTV stream.
- Recognition uses V3's trained MobileNetV2+ArcFace model and DB-stored
  embeddings (NOT InsightFace) — batch-scoped via config.
- Liveness (MiniFASNet anti-spoof) always runs before attendance is marked.
- Stream transport to frontend: MJPEG HTTP stream; recognition events
  delivered via HTTP polling.

## Architecture

```
CCTV Camera (RTSP)
   │
   ▼
cctv_service.py  (background thread, started from main.py like scheduler)
   │  loop: read frame → person detection → head-crop → liveness →
   │        identify_face (ArcFace + DB) → mark_attendance_logic
   │
   ├── latest annotated frame (JPEG)  ──►  GET /cctv/stream   (MJPEG)
   ├── recent events                   ──►  GET /cctv/events   (HTTP poll)
   └── status state                    ──►  GET /cctv/status
```

All models already loaded at import time in V3 (`model_service.py`,
`liveness_service.py`, `yolo_service.py`) are reused — no duplicate model
instances. A new COCO person detector is added.

## Components

### Backend (new/modified files under `backend/`)

#### NEW `app/services/person_detector.py`
- Loads YOLOv8 COCO model (`yolov8n.pt`) from `backend/model/`.
- `detect_persons(frame) -> list[(x1, y1, x2, y2)]` — returns person bboxes
  (class 0) above a confidence threshold, mirroring `yolo_service.py` style.
- Person detection is used because CCTV faces are small/distant; a face
  detector alone is unreliable on full CCTV frames (proven in the test app).
  A person bbox is cropped to the head region for recognition.

#### NEW `app/services/cctv_service.py`
- `CCTVService` singleton class with `start()` and `stop()`.
- Background thread (`threading.Thread`, daemon) that:
  - Opens the RTSP stream via `cv2.VideoCapture` (TCP transport), with a
    stream fallback list like the test app (video3 → video2 → video1) and
    auto-reconnect with backoff (~5s) if the stream drops.
  - Reads frames; runs the detection pipeline at a configurable interval
    (`CCTV_DETECT_INTERVAL`, ~2-3s) to keep CPU usage sane.
  - Downscales frames to `DETECT_WIDTH` (640) for fast YOLO inference;
    head crops are taken from the full-res frame for sharp faces (same
    strategy as the proven test app).
  - For each person: head-crop (top ~40% of person bbox) → upscale to
    ≥160px short side → `check_liveness(frame, face_bbox)` → if live →
    `identify_face(pil_img, db, batch_id)` → `mark_attendance_logic(db,
    student_id, score)`.
  - Publishes: latest annotated frame (JPEG-encoded, locked), the current
    detection boxes/labels, and an append-only deque of recent events.
- Crash protection: entire per-frame work is wrapped in try/except so a
  corrupt frame never kills the thread (lesson from the test app).
- Batches: uses the configured `CCTV_BATCH_ID` to scope recognition.
  `CCTV_BATCH_ID` is REQUIRED — if it is missing, the service logs an error
  at startup and does not start (recognition must stay batch-scoped; never
  search all batches from CCTV).

#### NEW `app/api/cctv.py`
- Router `cctv.router` with:
  - `GET /cctv/stream` → `StreamingResponse` of `multipart/x-mixed-replace`
    JPEG frames from the latest annotated frame. Auth: Bearer token accepted
    via query param `?token=` because `<img>` tags cannot send headers.
  - `GET /cctv/status` → enabled, connected, resolution, person count,
    last event.
  - `GET /cctv/events` → recent recognition events (name, confidence,
    status, message, timestamp).
  - `POST /cctv/toggle` → enable/disable the service (admin only).

#### MODIFIED `app/core/config.py`
- Add settings:
  - `CCTV_ENABLED: bool = False`
  - `CCTV_RTSP_URL: str = ""`
  - `CCTV_BATCH_ID: int | None = None`
  - `CCTV_DETECT_INTERVAL: float = 2.5`
  - `CCTV_STREAM_FALLBACKS: str = ""` (optional extra RTSP URLs)
- `.env` provides values; service only starts if `CCTV_ENABLED`.

#### MODIFIED `app/main.py`
- `app.include_router(cctv.router, tags=["CCTV"])`
- Start the CCTV service on startup (guarded by `CCTV_ENABLED`) — same
  pattern as `start_scheduler()`.

### Frontend (new/modified files under `frontend/src/`)

#### NEW `pages/CCTVPage.jsx`
- Protected route for roles `teacher`, `admin`.
- Shows the live annotated stream: `<img src="/cctv/stream?token=...">`
  (token from `localStorage`).
- Status panel: service enabled/connected, resolution, person count.
- Recent recognitions feed: polls `/cctv/events` every ~2s, renders the
  last N events with badges (pending/unrecognized/rejected/skipped/error).
- Enable/Disable toggle (visible only to admin) hitting `/cctv/toggle`.

#### MODIFIED `App.jsx`
- Add route: `/teacher/cctv` → `<CCTVPage />` (roles teacher, admin).

#### MODIFIED `components/Sidebar.jsx`
- Add "CCTV" link for teacher/admin.

## Data Flow (per detection)

1. Frame read from RTSP.
2. Person bboxes from YOLO COCO.
3. For each person: head region crop → upscale.
4. `check_liveness` — if spoofed, event `rejected` ("Spoof Detected") and skip.
5. `identify_face` — if below threshold, event `unrecognized` ("Unknown").
6. `mark_attendance_logic` — returns `pending` / `skipped` / `error`; event logged.

Events are recorded for every outcome and surfaced in `/cctv/events`.

## Error Handling

- RTSP drop → reconnect every ~5s with backoff.
- Corrupt frame / transient model error → try/except, thread stays alive,
  error logged.
- No current period → `mark_attendance_logic` returns `skipped` (existing
  behavior).
- Already marked → `skipped` (existing behavior in `mark_attendance_logic`).

## Config Example (.env)

```
CCTV_ENABLED=true
CCTV_RTSP_URL=rtsp://admin:123456@192.168.1.83:554/media/video3?rtsp_transport=tcp&tcp_nodelay=1
CCTV_BATCH_ID=1
CCTV_DETECT_INTERVAL=2.5
```

## Testing

1. Run backend standalone; confirm `CCTVService` starts and connects.
2. Verify a person in frame produces detection + event + DB attendance row.
3. Open `/cctv/stream?token=<jwt>` in browser → live annotated feed.
4. Poll `/cctv/events` → recognition events appear.
5. Toggle enable/disable via `/cctv/toggle` (admin) and confirm effect.
6. Confirm detections appear in the period review page (teacher).

## Out of Scope (future)

- Multi-camera DB registry (a `cameras` table); currently one camera via
  config with optional fallback URLs.
- WebSocket live events (HTTP polling used instead).
- CCTV face enrollment (enrollment stays on webcam via RegisterFacePage).
