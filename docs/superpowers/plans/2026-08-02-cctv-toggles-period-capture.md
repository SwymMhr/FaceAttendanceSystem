# CCTV Toggles + Period-Gated Auto-Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the CCTV service into two threads (display + worker) so the live view is never throttled by inference, add independent Detect/Recognize toggles (default OFF) and an admin-only Auto-Capture toggle (default ON) that only marks attendance during a scheduled period and fires at a random interval configurable in the frontend.

**Architecture:** `CCTVService` runs a display thread (reads RTSP at native FPS, publishes annotated MJPEG capped by `CCTV_STREAM_FPS`) and a worker thread (live detection/recognition for display only; auto-capture = detect → liveness → recognize → `mark_attendance_logic`, gated by `get_current_period(db, CCTV_BATCH_ID)` and scheduled at `random.uniform(min, max)`). Toggles/settings change at runtime via `POST /cctv/settings`; frontend shows three toggle buttons + interval inputs.

**Tech Stack:** Python 3.12, FastAPI 0.111, SQLAlchemy 2.0, OpenCV, ultralytics 8.2.18, PyTorch 2.3, React 18 (Vite), axios.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/core/config.py` | Modify | Add `CCTV_STREAM_FPS`, `CCTV_CAPTURE_MIN_INTERVAL`, `CCTV_CAPTURE_MAX_INTERVAL`; remove `CCTV_DETECT_INTERVAL` |
| `backend/.env` | Modify | Add stream-fps + capture-interval defaults; drop `CCTV_DETECT_INTERVAL` |
| `backend/app/services/cctv_service.py` | Modify | Two-thread service + toggle state + `update_settings` + period gate + random capture |
| `backend/test_cctv_service.py` | Modify | Tests for helpers, defaults, `update_settings` |
| `backend/app/api/cctv.py` | Modify | Status additions + `POST /cctv/settings` |
| `frontend/src/api.js` | Modify | Add `updateCctvSettings` |
| `frontend/src/pages/CCTVPage.jsx` | Modify | Toggle buttons + interval inputs + in-period badge |

---

### Task 1: Add config settings

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env`

- [ ] **Step 1: Update the CCTV settings block in config.py**

In `backend/app/core/config.py`, replace the current block (lines ~30-35):

```python
    # ── CCTV integration ─────────────────────────────────────────────────
    CCTV_ENABLED: bool = False
    CCTV_RTSP_URL: str = ""
    CCTV_STREAM_FALLBACKS: str = ""
    CCTV_BATCH_ID: int | None = None
    CCTV_DETECT_INTERVAL: float = 2.5
```

with:

```python
    # ── CCTV integration ─────────────────────────────────────────────────
    CCTV_ENABLED: bool = False
    CCTV_RTSP_URL: str = ""
    CCTV_STREAM_FALLBACKS: str = ""
    CCTV_BATCH_ID: int | None = None
    CCTV_STREAM_FPS: float = 15.0
    CCTV_CAPTURE_MIN_INTERVAL: float = 1.0
    CCTV_CAPTURE_MAX_INTERVAL: float = 5.0
```

`CCTV_DETECT_INTERVAL` is removed — the worker now runs continuously.

- [ ] **Step 2: Update backend/.env**

Open `backend/.env`. If a line `CCTV_DETECT_INTERVAL=...` exists, remove it. Append (do not change existing values in the file):

```
CCTV_STREAM_FPS=15
CCTV_CAPTURE_MIN_INTERVAL=1
CCTV_CAPTURE_MAX_INTERVAL=5
```

- [ ] **Step 3: Verify config loads**

Run (from `backend/`):

```powershell
python -c "from app.core.config import settings; print(settings.CCTV_STREAM_FPS, settings.CCTV_CAPTURE_MIN_INTERVAL, settings.CCTV_CAPTURE_MAX_INTERVAL)"
```

Expected: `15.0 1.0 5.0`

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py backend/.env
git commit -m "feat(cctv): add stream fps + capture interval config"
```

---

### Task 2: Add pure helper functions (validate / random delay / period gate)

**Files:**
- Modify: `backend/app/services/cctv_service.py`
- Test: `backend/test_cctv_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_cctv_service.py` (before the `if __name__` block):

```python
def test_validate_interval():
    """Interval window must be positive and min <= max."""
    from app.services.cctv_service import validate_interval
    assert validate_interval(1.0, 5.0) is None
    assert validate_interval(None, None) is None
    assert validate_interval(0.5, 0.5) is None
    assert validate_interval(0, 5.0) == "capture_min must be > 0"
    assert validate_interval(1.0, 0) == "capture_max must be > 0"
    assert validate_interval(7.0, 3.0) == "capture_min cannot exceed capture_max"


def test_random_capture_delay():
    """Random delay stays inside [min, max); equal bounds return the value."""
    from app.services.cctv_service import random_capture_delay
    assert random_capture_delay(2.0, 2.0) == 2.0
    for _ in range(500):
        d = random_capture_delay(1.0, 5.0)
        assert 1.0 <= d < 5.0, f"delay out of bounds: {d}"


def test_should_capture():
    """Auto-capture only fires when in a period AND the timer elapsed."""
    from app.services.cctv_service import should_capture
    assert should_capture(True, 10.0, 5.0) is True
    assert should_capture(False, 10.0, 5.0) is False
    assert should_capture(True, 3.0, 5.0) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: FAIL with `ImportError` / `AttributeError` (functions do not exist yet).

- [ ] **Step 3: Add the helper functions**

In `backend/app/services/cctv_service.py`, add `import random` to the imports, and add these functions right after `stream_urls()` (before `class CCTVService`):

```python
def validate_interval(min_interval, max_interval):
    """Return an error message string if the capture interval window is
    invalid, otherwise None."""
    if min_interval is not None and min_interval <= 0:
        return "capture_min must be > 0"
    if max_interval is not None and max_interval <= 0:
        return "capture_max must be > 0"
    if min_interval is not None and max_interval is not None and min_interval > max_interval:
        return "capture_min cannot exceed capture_max"
    return None


def random_capture_delay(min_interval, max_interval):
    """Random delay (seconds) before the next auto-capture."""
    return random.uniform(min_interval, max_interval)


def should_capture(in_period, now, next_capture):
    """Auto-capture fires only inside a scheduled period AND once the random
    timer has elapsed."""
    return in_period and now >= next_capture
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: prints `All CCTV service tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cctv_service.py backend/test_cctv_service.py
git commit -m "feat(cctv): add interval validation and capture gate helpers"
```

---

### Task 3: Rework CCTVService into two threads + runtime settings

**Files:**
- Modify: `backend/app/services/cctv_service.py`
- Test: `backend/test_cctv_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_cctv_service.py`:

```python
def test_toggle_defaults():
    """Live detection/recognition default OFF; auto-capture defaults ON."""
    from app.services.cctv_service import CCTVService
    from app.core.config import settings
    svc = CCTVService()
    assert svc._detect_enabled is False
    assert svc._recognize_enabled is False
    assert svc._auto_capture_enabled is True
    assert svc._capture_min_interval == settings.CCTV_CAPTURE_MIN_INTERVAL
    assert svc._capture_max_interval == settings.CCTV_CAPTURE_MAX_INTERVAL
    assert svc._in_period is False


def test_update_settings():
    """update_settings applies partial updates and rejects bad intervals."""
    from app.services.cctv_service import CCTVService
    svc = CCTVService()
    st = svc.update_settings(detect=True, capture_min=2.0, capture_max=6.0)
    assert st["detect_enabled"] is True
    assert st["recognize_enabled"] is False
    assert st["auto_capture_enabled"] is True
    assert st["capture_min_interval"] == 2.0
    assert st["capture_max_interval"] == 6.0
    try:
        svc.update_settings(capture_min=7.0, capture_max=3.0)
        raise AssertionError("expected ValueError for min > max")
    except ValueError:
        pass
    try:
        svc.update_settings(capture_min=0)
        raise AssertionError("expected ValueError for non-positive interval")
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: FAIL with `AttributeError` (`CCTVService` has no `_detect_enabled` / `update_settings`).

- [ ] **Step 3: Rewrite cctv_service.py with the two-thread design**

Overwrite `backend/app/services/cctv_service.py` entirely with:

```python
# app/services/cctv_service.py
# Background CCTV service. Started once from app/main.py (like the
# scheduler). Two threads mirror the proven test app (cctv_viewer.py):
#   · DISPLAY THREAD: reads the RTSP stream at native FPS, publishes an
#     annotated MJPEG frame (capped by CCTV_STREAM_FPS). Never runs heavy
#     inference, so the live view is never throttled by the worker.
#   · WORKER THREAD: processes the latest frame in the background —
#     live detection/recognition (toggles, display only) and the
#     period-gated auto-capture attendance pipeline (the ONLY writer of
#     attendance rows). All state is thread-safe.

import random
import threading
import time
from collections import deque
from datetime import datetime, timezone

import cv2
from PIL import Image

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.person_detector import detect_persons
from app.services.liveness_service import check_liveness
from app.services.recognition_service import identify_face
from app.services.attendance_service import get_current_period, mark_attendance_logic

HEAD_FRACTION = 0.4
MIN_HEAD_UPSCALE = 160.0
DETECT_WIDTH = 640
EVENT_QUEUE_MAX = 100
RECONNECT_BACKOFF_S = 5.0
JPEG_QUALITY = 80
PERIOD_CHECK_INTERVAL = 30.0
WORKER_SLEEP = 0.02


def head_region(box):
    """Return the head region (top 40%) of a person bbox as (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = box
    return (x1, y1, x2, y1 + int((y2 - y1) * HEAD_FRACTION))


def stream_urls():
    """Ordered RTSP URLs to try: the primary CCTV_RTSP_URL, then the
    comma-separated CCTV_STREAM_FALLBACKS (e.g. video3 → video2 → video1)."""
    urls = [settings.CCTV_RTSP_URL]
    if settings.CCTV_STREAM_FALLBACKS:
        urls += [u.strip() for u in settings.CCTV_STREAM_FALLBACKS.split(",") if u.strip()]
    return urls


def validate_interval(min_interval, max_interval):
    """Return an error message string if the capture interval window is
    invalid, otherwise None."""
    if min_interval is not None and min_interval <= 0:
        return "capture_min must be > 0"
    if max_interval is not None and max_interval <= 0:
        return "capture_max must be > 0"
    if min_interval is not None and max_interval is not None and min_interval > max_interval:
        return "capture_min cannot exceed capture_max"
    return None


def random_capture_delay(min_interval, max_interval):
    """Random delay (seconds) before the next auto-capture."""
    return random.uniform(min_interval, max_interval)


def should_capture(in_period, now, next_capture):
    """Auto-capture fires only inside a scheduled period AND once the random
    timer has elapsed."""
    return in_period and now >= next_capture


class CCTVService:
    def __init__(self):
        self._thread = None
        self._worker = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_jpeg = None
        self._latest_frame = None       # most recent raw frame (worker input)
        self._detections = []           # list of dicts: box, label, color
        self._events = deque(maxlen=EVENT_QUEUE_MAX)
        self._connected = False
        self._resolution = None
        self._last_error = None
        self._detect_enabled = False
        self._recognize_enabled = False
        self._auto_capture_enabled = True
        self._capture_min_interval = settings.CCTV_CAPTURE_MIN_INTERVAL
        self._capture_max_interval = settings.CCTV_CAPTURE_MAX_INTERVAL
        self._in_period = False
        self._next_capture = 0.0

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
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
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
                "detect_enabled": self._detect_enabled,
                "recognize_enabled": self._recognize_enabled,
                "auto_capture_enabled": self._auto_capture_enabled,
                "capture_min_interval": self._capture_min_interval,
                "capture_max_interval": self._capture_max_interval,
                "in_period": self._in_period,
            }

    def get_events(self, limit=50):
        with self._lock:
            return list(self._events)[-limit:]

    def get_latest_jpeg(self):
        with self._lock:
            return self._latest_jpeg

    # ── settings ──────────────────────────────────────────────────────
    def update_settings(self, detect=None, recognize=None, auto_capture=None,
                        capture_min=None, capture_max=None):
        """Apply a partial runtime update. Raises ValueError on invalid
        interval values. Returns the fresh status dict."""
        error = validate_interval(capture_min, capture_max)
        if error:
            raise ValueError(error)
        with self._lock:
            if detect is not None:
                self._detect_enabled = bool(detect)
            if recognize is not None:
                self._recognize_enabled = bool(recognize)
            if auto_capture is not None:
                self._auto_capture_enabled = bool(auto_capture)
            if capture_min is not None:
                self._capture_min_interval = float(capture_min)
            if capture_max is not None:
                self._capture_max_interval = float(capture_max)
        return self.get_status()

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
        urls = stream_urls()
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
        """Display thread: read frames at native FPS, publish an annotated
        JPEG at most CCTV_STREAM_FPS times/sec."""
        last_publish = 0.0
        publish_interval = 1.0 / settings.CCTV_STREAM_FPS
        while self._running:
            ret, frame = cap.read()
            if not ret:
                print("[CCTV] Stream read failed — reconnecting.")
                return
            with self._lock:
                self._latest_frame = frame
                detections = list(self._detections)
            annotated = self._draw_overlay(frame, detections)
            now = time.time()
            if now - last_publish < publish_interval:
                continue
            last_publish = now
            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()

    def _draw_overlay(self, frame, detections):
        annotated = frame.copy()
        for d in detections:
            x1, y1, x2, y2 = d["box"]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), d["color"], 2)
            cv2.putText(annotated, d["label"], (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, d["color"], 2)
        return annotated

    def _worker_loop(self):
        """Worker thread: live detection/recognition + period-gated
        auto-capture on the latest frame."""
        next_period_check = 0.0
        while self._running:
            try:
                with self._lock:
                    do_detect = self._detect_enabled
                    do_recognize = self._recognize_enabled
                    do_capture = self._auto_capture_enabled

                if not (do_detect or do_recognize or do_capture):
                    time.sleep(0.5)
                    continue

                now = time.time()
                if now >= next_period_check:
                    in_period = self._refresh_period_state()
                    next_period_check = now + PERIOD_CHECK_INTERVAL
                else:
                    with self._lock:
                        in_period = self._in_period

                with self._lock:
                    frame = self._latest_frame

                if do_capture:
                    if should_capture(in_period, now, self._next_capture) and frame is not None:
                        self._run_attendance_capture(frame)
                        with self._lock:
                            self._next_capture = time.time() + random_capture_delay(
                                self._capture_min_interval, self._capture_max_interval)

                if do_detect or do_recognize:
                    if frame is not None:
                        self._update_live_detections(frame, do_recognize)

                time.sleep(WORKER_SLEEP)
            except Exception as e:
                print(f"[CCTV] Worker error: {e}")
                time.sleep(WORKER_SLEEP)

    def _refresh_period_state(self):
        in_period = False
        db = SessionLocal()
        try:
            period = get_current_period(db, settings.CCTV_BATCH_ID)
            in_period = period is not None
        except Exception as e:
            print(f"[CCTV] Period check error: {e}")
        finally:
            db.close()
        with self._lock:
            if in_period != self._in_period:
                print(f"[CCTV] Class period {'started' if in_period else 'ended'}.")
            self._in_period = in_period
        return in_period

    def _update_live_detections(self, frame, do_recognize):
        """Detect persons on the latest frame; optionally recognize each
        (display only — no liveness, no attendance, no events)."""
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
                name = "Person"
                color = (0, 255, 0)
                if do_recognize:
                    name, _, color = self._live_recognize_person(frame, box, db)
                detections.append({"box": box, "label": name, "color": color})
        finally:
            db.close()
        with self._lock:
            self._detections = detections

    def _live_recognize_person(self, frame, box, db):
        """Display-only recognition of a single person bbox. Returns
        (name, confidence, color). No liveness, no attendance, no event."""
        x1, y1, x2, y2 = box
        if (y2 - y1) < 20:
            return "Person", 0.0, (0, 255, 0)

        hx1, hy1, hx2, hy2 = head_region(box)
        head = frame[max(0, hy1):hy2, max(0, hx1):hx2]
        if head.size == 0 or head.shape[0] < 5 or head.shape[1] < 5:
            return "Person", 0.0, (0, 255, 0)

        short = min(head.shape[0], head.shape[1])
        if short < MIN_HEAD_UPSCALE:
            s = MIN_HEAD_UPSCALE / short
            head = cv2.resize(head, (int(head.shape[1] * s), int(head.shape[0] * s)),
                              interpolation=cv2.INTER_CUBIC)

        pil = Image.fromarray(cv2.cvtColor(head, cv2.COLOR_BGR2RGB))
        try:
            student, score, _ = identify_face(pil, db, batch_id=settings.CCTV_BATCH_ID)
        except Exception:
            return "Person", 0.0, (0, 255, 0)
        if not student:
            return "Unknown", round(score, 4), (0, 165, 255)
        return student.student_name, round(score, 4), (0, 255, 0)

    def _run_attendance_capture(self, frame):
        """Full auto-capture pipeline: detect → per person: liveness →
        recognize → mark_attendance_logic → log event. The ONLY writer of
        attendance rows."""
        h, w = frame.shape[:2]
        scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
        work = frame
        inv_scale = 1.0
        if scale < 1.0:
            work = cv2.resize(frame, (DETECT_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
            inv_scale = 1.0 / scale

        persons = detect_persons(work)
        db = SessionLocal()
        try:
            for (px1, py1, px2, py2) in persons:
                box = (int(px1 * inv_scale), int(py1 * inv_scale),
                       int(px2 * inv_scale), int(py2 * inv_scale))
                name, confidence, status, message, _ = self._attendance_recognize_person(frame, box, db)
                self._log_event(name, confidence, status, message)
        finally:
            db.close()

    def _attendance_recognize_person(self, frame, box, db):
        """Recognize a single person bbox for attendance. Returns
        (name, conf, status, message, color)."""
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

- [ ] **Step 4: Run tests to verify they pass**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: prints `All CCTV service tests passed`.

- [ ] **Step 5: Sanity-check the module imports cleanly (no service start)**

Run (from `backend/`):

```powershell
python -c "from app.services.cctv_service import cctv_service; print(cctv_service.get_status()['detect_enabled'], cctv_service.get_status()['auto_capture_enabled'])"
```

Expected: `False True`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cctv_service.py backend/test_cctv_service.py
git commit -m "feat(cctv): split display/worker threads with detect-recognize-auto toggles"
```

---

### Task 4: API — status fields + POST /cctv/settings

**Files:**
- Modify: `backend/app/api/cctv.py`

- [ ] **Step 1: Add the settings schema + endpoint**

In `backend/app/api/cctv.py`, add `from pydantic import BaseModel` to the imports, then add this schema after the `router = ...` line:

```python
class CctvSettings(BaseModel):
    detect: bool | None = None
    recognize: bool | None = None
    auto_capture: bool | None = None
    capture_min: float | None = None
    capture_max: float | None = None
```

Add the endpoint at the bottom of the file (after `/toggle`):

```python
@router.post("/settings")
def update_settings(payload: CctvSettings, _: None = Depends(require_role("admin"))):
    try:
        return cctv_service.update_settings(
            detect=payload.detect,
            recognize=payload.recognize,
            auto_capture=payload.auto_capture,
            capture_min=payload.capture_min,
            capture_max=payload.capture_max,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

The `/status` endpoint already returns `cctv_service.get_status()`, which now includes `detect_enabled`, `recognize_enabled`, `auto_capture_enabled`, `capture_min_interval`, `capture_max_interval`, and `in_period` — no change needed there.

- [ ] **Step 2: Import-check the router**

Run (from `backend/`):

```powershell
python -c "from app.api.cctv import router; print('router ok')"
```

Expected: `router ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/cctv.py
git commit -m "feat(cctv): add /cctv/settings endpoint + status toggle fields"
```

---

### Task 5: Frontend — toggle buttons + interval inputs

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/pages/CCTVPage.jsx`

- [ ] **Step 1: Add the api helper**

In `frontend/src/api.js`, right after the existing `toggleCctv` function (around line 311), add:

```javascript
export async function updateCctvSettings(payload) {
  const res = await api.post("/cctv/settings", payload);
  return res.data;
}
```

- [ ] **Step 2: Update CCTVPage.jsx**

Overwrite `frontend/src/pages/CCTVPage.jsx` entirely with:

```jsx
import { useEffect, useState } from "react";
import { getCctvStatus, getCctvEvents, toggleCctv, updateCctvSettings, getRole } from "../api";
import PageHeader from "../components/PageHeader";

const STATUS_BADGE = {
  pending: "bg-info text-dark",
  skipped: "bg-warning text-dark",
  error: "bg-danger",
  unrecognized: "bg-secondary",
  rejected: "bg-danger text-white",
};

const API_BASE_URL = "http://localhost:8000";

function ToggleBtn({ label, active, onClick, disabled }) {
  return (
    <button
      className={`btn btn-sm ${active ? "btn-success" : "btn-outline-secondary"}`}
      onClick={onClick}
      disabled={disabled}
    >
      {label}: {active ? "ON" : "OFF"}
    </button>
  );
}

export default function CCTVPage() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [streamKey, setStreamKey] = useState(0);
  const [captureMin, setCaptureMin] = useState("1");
  const [captureMax, setCaptureMax] = useState("5");
  const [saveMsg, setSaveMsg] = useState("");
  const role = getRole();

  useEffect(() => {
    const load = () => {
      getCctvStatus()
        .then((s) => {
          setStatus(s);
          if (s.capture_min_interval != null) setCaptureMin(String(s.capture_min_interval));
          if (s.capture_max_interval != null) setCaptureMax(String(s.capture_max_interval));
        })
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
      setStreamKey((k) => k + 1);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to toggle CCTV service.");
    }
  };

  const handleSetting = async (key, value) => {
    try {
      const res = await updateCctvSettings({ [key]: value });
      setStatus(res);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update setting.");
    }
  };

  const handleSaveInterval = async () => {
    setSaveMsg("");
    try {
      const res = await updateCctvSettings({
        capture_min: parseFloat(captureMin),
        capture_max: parseFloat(captureMax),
      });
      setStatus(res);
      setSaveMsg("Saved");
    } catch (err) {
      setSaveMsg(err.response?.data?.detail || "Save failed");
    }
  };

  const running = status?.running;

  return (
    <div className="page">
      <PageHeader
        title="CCTV Live View"
        subtitle="Automatic attendance from the classroom camera. Auto-capture runs only during scheduled class periods."
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
          <span className={`badge ${status?.in_period ? "bg-success" : "bg-warning text-dark"}`}>
            {status?.in_period ? "In class period" : "Outside class period"}
          </span>
          {role === "admin" && (
            <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={handleToggle}>
              {running ? "Stop" : "Start"}
            </button>
          )}
        </div>

        <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
          <ToggleBtn
            label="Detect"
            active={!!status?.detect_enabled}
            onClick={() => handleSetting("detect", !status.detect_enabled)}
          />
          <ToggleBtn
            label="Recognize"
            active={!!status?.recognize_enabled}
            onClick={() => handleSetting("recognize", !status.recognize_enabled)}
          />
          {role === "admin" && (
            <ToggleBtn
              label="Auto Capture"
              active={!!status?.auto_capture_enabled}
              onClick={() => handleSetting("auto_capture", !status.auto_capture_enabled)}
            />
          )}
        </div>

        {role === "admin" && (
          <div className="d-flex align-items-center gap-2 mb-3">
            <label className="small text-muted mb-0">Capture interval (s):</label>
            <input
              type="number" min="0.5" step="0.5" value={captureMin}
              onChange={(e) => setCaptureMin(e.target.value)}
              className="form-control form-control-sm" style={{ width: 90 }}
            />
            <span>–</span>
            <input
              type="number" min="0.5" step="0.5" value={captureMax}
              onChange={(e) => setCaptureMax(e.target.value)}
              className="form-control form-control-sm" style={{ width: 90 }}
            />
            <button className="btn btn-sm btn-primary" onClick={handleSaveInterval}>Save</button>
            {saveMsg && <span className="small text-muted">{saveMsg}</span>}
          </div>
        )}

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

- [ ] **Step 3: Build the frontend**

Run (from `frontend/`):

```powershell
npm.cmd run build
```

Expected: Vite build succeeds, no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.js frontend/src/pages/CCTVPage.jsx
git commit -m "feat(cctv): add detect/recognize/auto-capture toggles + interval config to CCTV page"
```

---

### Task 6: Manual E2E verification

- [ ] **Step 1: Restart the backend**

Find the running uvicorn on port 8000 and stop it, then restart with logs:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "uvicorn" -and $_.CommandLine -match "8000" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2
Start-Process -FilePath python -ArgumentList "-m","uvicorn","app.main:app","--port","8000" -WorkingDirectory "D:\Misc\github repo test\V4\backend" -RedirectStandardOutput "$env:TEMP\opencode\uvicorn_cctv3.log" -RedirectStandardError "$env:TEMP\opencode\uvicorn_cctv3.err.log" -WindowStyle Hidden
Start-Sleep -Seconds 8
```

Then confirm the service came up and connected (check the log):

```powershell
Get-Content "$env:TEMP\opencode\uvicorn_cctv3.log"
```

Expected: startup lines plus `[CCTV] Connected: ...` (or a fallback reconnect note).

- [ ] **Step 2: Get an admin token and check status fields**

```powershell
$body = @{ email = "admin@test.com"; password = "admin123" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/login" -ContentType "application/json" -Body $body
$h = @{ Authorization = "Bearer $($login.access_token)" }
$st = Invoke-RestMethod -Uri "http://localhost:8000/cctv/status" -Headers $h
$st | ConvertTo-Json -Depth 3
```

Expected: JSON containing `detect_enabled: False`, `recognize_enabled: False`, `auto_capture_enabled: True`, `capture_min_interval: 1`, `capture_max_interval: 5`, `in_period: False` (or True depending on the actual schedule), `connected: True`.

- [ ] **Step 3: Exercise /cctv/settings (admin)**

```powershell
$s1 = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/cctv/settings" -Headers $h -ContentType "application/json" -Body '{"detect":true,"capture_min":2,"capture_max":4}'
$s1.detect_enabled
$s1.capture_min_interval
```

Expected: `True`, `2`. Then verify invalid input is rejected:

```powershell
try { Invoke-RestMethod -Method Post -Uri "http://localhost:8000/cctv/settings" -Headers $h -ContentType "application/json" -Body '{"capture_min":9,"capture_max":3}' } catch { $_.Exception.Response.StatusCode.value__ }
```

Expected: `400`.

Reset to defaults afterwards:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/cctv/settings" -Headers $h -ContentType "application/json" -Body '{"detect":false}'
```

- [ ] **Step 4: Verify the frontend**

Open `http://localhost:5173`, log in as admin, go to CCTV Live. Confirm:
- Stream plays and updates smoothly (detect/recognize OFF by default → no boxes, high FPS).
- Three toggles render; Detect/Recognize are OFF, Auto Capture is ON.
- Toggling Detect ON shows green person boxes without stalling the stream.
- Toggling Recognize ON adds names on boxes.
- Interval inputs present for admin; saving changes reflects in a "Saved" message; the status panel shows the new min/max.
- "In class period" badge reflects the real schedule.

- [ ] **Step 5: Commit any leftover fix if found**

If any adjustment was needed during verification, commit it with a descriptive message; otherwise mark this step done.

---

## Self-Review Notes

- Spec coverage: Detect/Recognize default OFF (Task 3), Auto-Capture ON admin-only (Tasks 3+5), two-thread live view (Task 3), period gate reusing `get_current_period` (Task 3), random interval frontend-configurable (Tasks 1+4+5), attendance only via auto-capture (Task 3 `_run_attendance_capture`), events = auto-capture only (Task 3).
- All code shown in full; no TODOs/placeholders.
- Name consistency: `validate_interval`/`random_capture_delay`/`should_capture`/`update_settings`/`_detect_enabled`/`_recognize_enabled`/`_auto_capture_enabled`/`capture_min_interval`/`capture_max_interval`/`in_period` used identically across service, API, and frontend.
