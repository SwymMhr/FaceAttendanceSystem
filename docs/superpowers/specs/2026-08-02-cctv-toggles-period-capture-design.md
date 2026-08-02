# CCTV FPS Toggles + Period-Gated Auto-Capture Design — V4

Date: 2026-08-02

Status: Approved (2026-08-02)

## Goal

Give the CCTV live view **independent Detect / Recognize toggles** so that live
recognition no longer throttles the stream FPS, and make **auto-attendance
capture period-gated** with a **frontend-configurable random interval**.

Today one single background thread reads a frame and, every `CCTV_DETECT_INTERVAL`
(~2.5s), runs the whole pipeline (detect + liveness + recognize + mark
attendance). That caps the live view to ~0.4 FPS and ties attendance to the same
timer. This design splits the work into two threads (exactly like the proven test
app `cctv_viewer.py`) and decouples attendance from the live view.

## Requirements

- **Two separate toggles**: Live Detection (`D`-style) and Live Recognition
  (`R`-style), exactly like the test app. Both default **OFF**.
- **Live view never throttled**: the display thread publishes frames at the
  camera's native FPS (capped only by a stream FPS setting); the slow
  detection/recognition work runs in a background worker on the *latest* frame.
- **Auto-capture** (`A`-style): third toggle, default **ON**, **admin-only**.
- **Period gate**: auto-capture runs **only** while a scheduled period is in
  session for `CCTV_BATCH_ID`. Outside the window it does *nothing* (no
  recognition work) and re-checks periodically so it auto-resumes when class
  starts.
- **Random interval**: after each capture, the next one is scheduled at
  `random.uniform(min_interval, max_interval)`. Min/max are **editable in the
  frontend** (number inputs), with config defaults.
- **Attendance is written ONLY by auto-capture.** Live recognition is
  display-only — it draws names on boxes, never calls `mark_attendance_logic`,
  and never logs events. Events feed = auto-capture outcomes only.
- All settings change at runtime, no service restart.

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │                cctv_service.py             │
                    │                                             │
 RTSP ─────────────▶│  DISPLAY THREAD (reads at native FPS)      │
                    │   · latest frame → shared _latest_frame     │
                    │   · draw latest _detections overlay         │
                    │   · publish annotated JPEG (≤ stream_fps)   │
                    │                                             │
                    │  WORKER THREAD (background, latest frame)   │
                    │   · live detection  (detect toggle ON)      │
                    │   · live recognition (recognize toggle ON)  │
                    │   · auto-capture: period-gated, random timer │
                    │        → mark_attendance_logic + events     │
                    └─────────────────────────────────────────────┘
                        │             │              │
                    /cctv/stream  /cctv/status   /cctv/events
```

State sharing mirrors `cctv_viewer.py`: the display thread owns the camera
`cap`, writes `_latest_frame` + publishes JPEG; the worker reads
`_latest_frame` and writes `_detections`; the display thread draws
`_detections` on the next frame it publishes.

## Components

### Backend — refactor `app/services/cctv_service.py`

New thread-safe state (defaults):

- `_detect_enabled: bool = False`
- `_recognize_enabled: bool = False`
- `_auto_capture_enabled: bool = True`
- `_capture_min_interval: float = settings.CCTV_CAPTURE_MIN_INTERVAL` (1.0)
- `_capture_max_interval: float = settings.CCTV_CAPTURE_MAX_INTERVAL` (5.0)
- `_in_period: bool = False` (cached by the worker; surfaced in status)
- `_latest_frame` (numpy array, guarded) — shared with the worker

Threads (both daemon, started/stopped in `start()` / `stop()`):

- **Display thread** = existing `_run`/`_camera_loop`, reworked:
  - Read frame → store `_latest_frame` → draw overlay → publish JPEG, but
    publish at most `settings.CCTV_STREAM_FPS` times/sec (bandwidth cap).
  - Never runs heavy inference.
  - Reconnect/backoff logic unchanged.
- **Worker thread** = new `_worker_loop`:
  - Loop: grab toggles + latest frame; tiny sleep (`0.02s`) between iterations
    so it never busy-spins.
  - **Auto-capture** (if enabled):
    - Check period state (DB `get_current_period(db, CCTV_BATCH_ID)`); update
      `_in_period` for status. When `auto_capture` is OFF, period is re-checked
      every `PERIOD_CHECK_INTERVAL` (30s) just to keep `_in_period` fresh.
    - If `in_period` and `now >= _next_capture`: run the full attendance
      capture on the latest frame, then
      `_next_capture = now + random.uniform(min, max)`.
    - If NOT in period: nothing runs; period re-check resumes it automatically.
  - **Live detection** (if detect or recognize ON): YOLO on a downscaled
    latest frame → update `_detections`. If recognize ON, also recognize each
    person (no liveness, no attendance, no event) and label the box.
  - Crash protection: per-iteration try/except keeps the thread alive.

Recognition helpers refactored (replacing `_process_frame` /
`_recognize_person`):

- `_live_recognize_person(frame, box, db)` → `(name, confidence, color)`.
  Head crop → upscale → `identify_face(pil, db, batch_id)`. Display only.
- `_attendance_recognize_person(frame, box, db)` →
  `(name, confidence, status, message, color)`. Existing behavior:
  head crop → upscale → **liveness (MiniFASNet, always)** → `identify_face`
  → `mark_attendance_logic` → `_log_event`.
- `_run_attendance_capture(frame)`: YOLO detect → for each person →
  `_attendance_recognize_person`. Reuses the existing `SessionLocal()` pattern.

### Backend — `app/api/cctv.py`

- `GET /cctv/status` adds: `detect_enabled`, `recognize_enabled`,
  `auto_capture_enabled`, `capture_min_interval`, `capture_max_interval`,
  `in_period`.
- `POST /cctv/settings` (admin only) — Pydantic body, all optional:
  `{detect?, recognize?, auto_capture?, capture_min?, capture_max?}`.
  Validation: intervals must be `> 0` and `min <= max`. Applies at runtime.

### Backend — `app/core/config.py`

- `CCTV_STREAM_FPS: float = 15.0` — caps MJPEG publish rate.
- `CCTV_CAPTURE_MIN_INTERVAL: float = 1.0`
- `CCTV_CAPTURE_MAX_INTERVAL: float = 5.0`
- `CCTV_DETECT_INTERVAL` no longer used (worker runs continuously); removed
  from config and `.env`.

### Frontend

`app/api.js`:

- `updateCctvSettings(payload)` → `POST /cctv/settings`.

`pages/CCTVPage.jsx`:

- Three toggle buttons in the status panel: **Live Detection**, **Live
  Recognition**, **Auto Capture**. Active state comes from `/cctv/status`.
  Detect/Recognize visible to teacher+admin; Auto-Capture toggle admin-only.
- **Min / Max interval** number inputs (seconds) + Save button — admin only;
  on save calls `updateCctvSettings`.
- "In class period" badge driven by `in_period`.
- Event feed + stream unchanged (events now reflect only auto-capture).

## Data Flow

1. Display thread reads frame at native FPS, publishes annotated JPEG.
2. Worker, on each iteration:
   - Auto-capture ON + in period + timer due → full attendance capture
     (detect → liveness → recognize → `mark_attendance_logic` → event).
   - Detect/Recognize ON → update `_detections` (boxes, optional names).
3. Next display frame draws `_detections`; the browser never waits on the
   worker.

## Error Handling

- Worker iteration wrapped in try/except — corrupt frame / model error never
  kills the thread (existing lesson preserved).
- RTSP drop → display thread returns → reconnect with backoff (unchanged).
- Outside period → auto-capture silently idle, re-checks every 30s.
- Invalid settings (min > max, non-positive) → 400 from `/cctv/settings`.

## Config Example (.env additions)

```
CCTV_STREAM_FPS=15
CCTV_CAPTURE_MIN_INTERVAL=1
CCTV_CAPTURE_MAX_INTERVAL=5
```

## Testing

1. `python test_cctv_service.py` — extend with:
   - default toggle states (detect/recognize off, auto-capture on).
   - settings validation (min > max rejected, non-positive rejected).
   - random interval stays within `[min, max]`.
   - period-gate decision helper (in-period vs out-of-period).
2. Manual E2E against running servers:
   - Toggles on the page change FPS/boxes/names without stalling the stream.
   - Auto-capture writes pending attendance rows only during a scheduled
     window; outside it, no events are produced.
   - Interval inputs change capture cadence; invalid values rejected.

## Out of Scope (future)

- Persisting toggle state across server restarts (runtime-only, resets to
  defaults).
- Per-role fine-grained control beyond admin-only for auto-capture.
- WebSocket live events (HTTP polling remains).
