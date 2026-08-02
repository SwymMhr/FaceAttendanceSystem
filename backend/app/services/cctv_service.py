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
IOU_MATCH_THRESHOLD = 0.4
MAX_AREA_RATIO = 2.0
TRACK_TTL = 30.0


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


def iou(box_a, box_b):
    """Intersection-over-union of two (x1, y1, x2, y2) boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def match_tracks(boxes, tracks, iou_threshold, max_area_ratio):
    """Greedy one-to-one match of boxes to tracks. Returns a list parallel to
    `boxes`: the index of the best matched track, or None."""
    matches = [None] * len(boxes)
    used = set()
    for i, box in enumerate(boxes):
        area = (box[2] - box[0]) * (box[3] - box[1])
        best_idx = None
        best_score = 0.0
        for j, track in enumerate(tracks):
            if j in used:
                continue
            tb = track["box"]
            t_area = (tb[2] - tb[0]) * (tb[3] - tb[1])
            if t_area > 0 and area > 0 and max(area, t_area) / min(area, t_area) > max_area_ratio:
                continue
            score = iou(box, tb)
            if score >= iou_threshold and score > best_score:
                best_idx = j
                best_score = score
        if best_idx is not None:
            matches[i] = best_idx
            used.add(best_idx)
    return matches


def prune_tracks(tracks, now, ttl):
    """Return tracks whose last_seen is within `ttl` seconds of `now`."""
    return [t for t in tracks if now - t["last_seen"] <= ttl]


def is_handled(track, handled_students):
    """True if the track belongs to a student already recorded this period."""
    sid = track["student_id"]
    return sid is not None and sid in handled_students


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
        self._tracks = []              # worker-private: {box, student_id, last_seen}
        self._handled_students = set()  # worker-private: student ids recorded this period

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
        self._tracks = []
        self._handled_students = set()
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
        with self._lock:
            eff_min = capture_min if capture_min is not None else self._capture_min_interval
            eff_max = capture_max if capture_max is not None else self._capture_max_interval
            error = validate_interval(eff_min, eff_max)
            if error:
                raise ValueError(error)
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
            # Display overlay should not keep stale boxes once all live
            # inference toggles are off.
            if not self._detect_enabled and not self._recognize_enabled:
                self._detections = []
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
                now = time.time()
                with self._lock:
                    do_detect = self._detect_enabled
                    do_recognize = self._recognize_enabled
                    do_capture = self._auto_capture_enabled

                # Keep in_period fresh for status even when nothing is enabled.
                if now >= next_period_check:
                    in_period = self._refresh_period_state()
                    next_period_check = now + PERIOD_CHECK_INTERVAL
                else:
                    with self._lock:
                        in_period = self._in_period

                if not (do_detect or do_recognize or do_capture):
                    time.sleep(0.5)
                    continue

                with self._lock:
                    frame = self._latest_frame

                if do_capture:
                    if should_capture(in_period, now, self._next_capture) and frame is not None:
                        try:
                            self._run_attendance_capture(frame)
                        finally:
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
            started = in_period and not self._in_period
            if in_period != self._in_period:
                print(f"[CCTV] Class period {'started' if in_period else 'ended'}.")
            self._in_period = in_period
        if started:
            self._tracks.clear()
            self._handled_students.clear()
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
        attendance rows. Students already handled this period (track matched,
        student_id in _handled_students) are skipped entirely."""
        h, w = frame.shape[:2]
        scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
        work = frame
        inv_scale = 1.0
        if scale < 1.0:
            work = cv2.resize(frame, (DETECT_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
            inv_scale = 1.0 / scale

        persons = detect_persons(work)
        now = time.time()
        self._tracks = prune_tracks(self._tracks, now, TRACK_TTL)
        boxes = [(int(px1 * inv_scale), int(py1 * inv_scale),
                  int(px2 * inv_scale), int(py2 * inv_scale))
                 for (px1, py1, px2, py2) in persons]
        matches = match_tracks(boxes, self._tracks, IOU_MATCH_THRESHOLD, MAX_AREA_RATIO)

        db = SessionLocal()
        try:
            for box, m in zip(boxes, matches):
                if m is None:
                    track = {"box": box, "student_id": None, "last_seen": now}
                    self._tracks.append(track)
                else:
                    track = self._tracks[m]
                    track["box"] = box
                    track["last_seen"] = now

                if is_handled(track, self._handled_students):
                    continue

                name, confidence, status, message, _, db_id = \
                    self._attendance_recognize_person(frame, box, db)
                if db_id is not None:
                    track["student_id"] = db_id
                    self._handled_students.add(db_id)
                self._log_event(name, confidence, status, message)
        finally:
            db.close()

    def _attendance_recognize_person(self, frame, box, db):
        """Recognize a single person bbox for attendance. Returns
        (name, conf, status, message, color, db_id)."""
        x1, y1, x2, y2 = box
        ph = y2 - y1
        if ph < 20:
            return "Unknown", 0.0, "unrecognized", "Person too small", (0, 165, 255), None

        hx1, hy1, hx2, hy2 = head_region(box)
        head = frame[max(0, hy1):hy2, max(0, hx1):hx2]
        if head.size == 0 or head.shape[0] < 5 or head.shape[1] < 5:
            return "Unknown", 0.0, "unrecognized", "Empty head crop", (0, 165, 255), None

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
            return "Unknown", 0.0, "error", f"Liveness error: {e}", (0, 0, 255), None
        if not liveness["is_live"]:
            return "Spoof Detected", round(liveness["confidence"], 4), "rejected", \
                   "Anti-spoofing failed (CNN liveness)", (0, 0, 255), None

        # ── Recognition (ArcFace + DB) ────────────────────────────────
        pil = Image.fromarray(cv2.cvtColor(head, cv2.COLOR_BGR2RGB))
        student, score, db_id = identify_face(pil, db, batch_id=settings.CCTV_BATCH_ID)
        if not student:
            return "Unknown", round(score, 4), "unrecognized", \
                   "Face not recognized in configured batch", (0, 165, 255), None

        outcome = mark_attendance_logic(db, db_id, score)
        return student.student_name, round(score, 4), outcome.get("status"), \
               outcome.get("message", ""), (0, 255, 0), db_id


cctv_service = CCTVService()
