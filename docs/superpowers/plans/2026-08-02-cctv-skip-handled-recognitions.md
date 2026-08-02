# CCTV Skip Re-Recognition of Handled Students Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop auto-capture from re-recognizing students whose attendance was already recorded this class period, eliminating repeated `skipped` events in the Recent Recognitions feed.

**Architecture:** Add worker-private, period-scoped person tracking to `CCTVService`. Each auto-capture detects persons, matches their boxes to existing tracks by IoU (+ area-ratio guard), and skips the liveness→recognition→mark pipeline entirely for tracks whose `student_id` is in the period's `_handled_students` set. State clears when a new period starts. Unrecognized/spoof people (no `student_id`) are never skipped and keep being retried.

**Tech Stack:** Python 3.12, OpenCV, existing `backend/app/services/cctv_service.py`, existing test harness `backend/test_cctv_service.py` (`python test_cctv_service.py`).

---

### Task 1: Pure tracking helpers + tests

**Files:**
- Modify: `backend/app/services/cctv_service.py` (constants block ~line 28-35; helpers after `should_capture` ~line 73)
- Test: `backend/test_cctv_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_cctv_service.py`:

```python
def test_iou():
    """IoU: identical = 1.0, disjoint = 0.0, overlap computed correctly."""
    from app.services.cctv_service import iou
    a = (0, 0, 10, 10)
    assert iou(a, a) == 1.0
    assert iou(a, (20, 20, 30, 30)) == 0.0
    c = (5, 0, 15, 10)
    assert abs(iou(a, c) - 50.0 / 150.0) < 1e-9, f"got {iou(a, c)}"


def test_match_tracks():
    """Boxes match overlapping tracks; disjoint / area-mismatched / already-used
    tracks are not matched (greedy one-to-one)."""
    from app.services.cctv_service import match_tracks
    tracks = [{"box": (0, 0, 10, 10), "student_id": 1, "last_seen": 0.0}]
    # overlapping box matches
    assert match_tracks([(0, 0, 10, 10)], tracks, 0.4, 2.0) == [0]
    # disjoint box does not match
    assert match_tracks([(50, 50, 60, 60)], tracks, 0.4, 2.0) == [None]
    # area ratio > 2.0 blocks the match (different person, same spot)
    assert match_tracks([(0, 0, 100, 100)], tracks, 0.4, 2.0) == [None]
    # two boxes can both overlap the track above threshold, but greedy binding
    # lets only one take it
    assert match_tracks([(0, 0, 10, 10), (1, 1, 11, 11)], tracks, 0.4, 2.0) == [0, None]


def test_prune_tracks():
    """Tracks unseen for longer than TTL are dropped."""
    from app.services.cctv_service import prune_tracks
    tracks = [
        {"box": (0, 0, 10, 10), "student_id": None, "last_seen": 0.0},
        {"box": (5, 5, 15, 15), "student_id": None, "last_seen": 100.0},
    ]
    kept = prune_tracks(tracks, 110.0, 30.0)
    assert len(kept) == 1
    assert kept[0]["last_seen"] == 100.0


def test_is_handled():
    """A track is handled only when its student_id is in the period set."""
    from app.services.cctv_service import is_handled
    assert is_handled({"student_id": 7}, {7}) is True
    assert is_handled({"student_id": None}, {7}) is False
    assert is_handled({"student_id": 8}, {7}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: FAIL with `ModuleNotFoundError`/`ImportError` or `NameError: name 'iou' is not defined`.

- [ ] **Step 3: Add constants + implement the helpers**

In `backend/app/services/cctv_service.py`, add to the constants block (after `WORKER_SLEEP = 0.02`):

```python
IOU_MATCH_THRESHOLD = 0.4
MAX_AREA_RATIO = 2.0
TRACK_TTL = 30.0
```

Add these module-level functions after `should_capture` (before `class CCTVService`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: `All CCTV service tests passed` (existing tests + the 4 new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cctv_service.py backend/test_cctv_service.py
git commit -m "feat(cctv): add IoU person-tracking helpers for skip logic"
```

---

### Task 2: Wire tracking into the auto-capture pipeline

**Files:**
- Modify: `backend/app/services/cctv_service.py` (`__init__` ~line 76, `start` ~line 98, `_refresh_period_state` ~line 315, `_attendance_recognize_person` ~line 409, `_run_attendance_capture` ~line 386)
- Test: `backend/test_cctv_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_cctv_service.py`:

```python
def test_attendance_capture_skips_handled_student():
    """A track already handled this period is not re-processed or re-logged."""
    import time
    from unittest.mock import patch
    import numpy as np
    from app.services.cctv_service import CCTVService
    svc = CCTVService()
    svc._handled_students = {42}
    svc._tracks = [{"box": (0, 0, 20, 60), "student_id": 42, "last_seen": time.time()}]
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch("app.services.cctv_service.detect_persons", return_value=[(0, 0, 20, 60)]), \
         patch.object(svc, "_attendance_recognize_person", return_value=("A", 1.0, "pending", "m", (0, 255, 0), 42)) as arp, \
         patch.object(svc, "_log_event") as le:
        svc._run_attendance_capture(frame)
    arp.assert_not_called()
    le.assert_not_called()


def test_attendance_capture_processes_new_student():
    """A new (unhandled) person runs the pipeline once, gets marked handled,
    and their track records the student_id."""
    import time
    from unittest.mock import patch
    import numpy as np
    from app.services.cctv_service import CCTVService
    svc = CCTVService()
    svc._handled_students = set()
    svc._tracks = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch("app.services.cctv_service.detect_persons", return_value=[(0, 0, 20, 60)]), \
         patch.object(svc, "_attendance_recognize_person", return_value=("A", 1.0, "pending", "Face recognized", (0, 255, 0), 42)) as arp, \
         patch.object(svc, "_log_event") as le:
        svc._run_attendance_capture(frame)
    arp.assert_called_once()
    le.assert_called_once()
    assert 42 in svc._handled_students
    assert svc._tracks[0]["student_id"] == 42


def test_period_start_clears_tracking_state():
    """A new class period resets tracks and the handled-students set."""
    from unittest.mock import patch
    from app.services.cctv_service import CCTVService
    svc = CCTVService()
    svc._in_period = False
    svc._tracks = [{"box": (0, 0, 10, 10), "student_id": 1, "last_seen": 1.0}]
    svc._handled_students = {1}
    with patch("app.services.cctv_service.get_current_period", return_value=object()):
        svc._refresh_period_state()
    assert svc._tracks == []
    assert svc._handled_students == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: FAIL on the 3 new tests (e.g. `AttributeError: 'CCTVService' object has no attribute '_handled_students'`).

- [ ] **Step 3: Initialize tracking state**

In `CCTVService.__init__`, after `self._next_capture = 0.0`:

```python
        self._tracks = []              # worker-private: {box, student_id, last_seen}
        self._handled_students = set()  # worker-private: student ids recorded this period
```

- [ ] **Step 4: Reset on start()**

In `start()`, immediately after `self._running = True` (and before the threads are started):

```python
        self._running = True
        self._tracks = []
        self._handled_students = set()
```

- [ ] **Step 5: Reset on period start**

Replace the body of `_refresh_period_state` with:

```python
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
```

- [ ] **Step 6: Return db_id from `_attendance_recognize_person`**

Update the docstring to `Returns (name, conf, status, message, color, db_id).` and append `None` (or `db_id`) to every return tuple:

```python
        if ph < 20:
            return "Unknown", 0.0, "unrecognized", "Person too small", (0, 165, 255), None
```

```python
        if head.size == 0 or head.shape[0] < 5 or head.shape[1] < 5:
            return "Unknown", 0.0, "unrecognized", "Empty head crop", (0, 165, 255), None
```

```python
        except Exception as e:
            return "Unknown", 0.0, "error", f"Liveness error: {e}", (0, 0, 255), None
```

```python
        if not liveness["is_live"]:
            return "Spoof Detected", round(liveness["confidence"], 4), "rejected", \
                   "Anti-spoofing failed (CNN liveness)", (0, 0, 255), None
```

```python
        if not student:
            return "Unknown", round(score, 4), "unrecognized", \
                   "Face not recognized in configured batch", (0, 165, 255), None
```

```python
        outcome = mark_attendance_logic(db, db_id, score)
        return student.student_name, round(score, 4), outcome.get("status"), \
               outcome.get("message", ""), (0, 255, 0), db_id
```

- [ ] **Step 7: Rework `_run_attendance_capture`**

Replace the whole method:

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: `All CCTV service tests passed`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/cctv_service.py backend/test_cctv_service.py
git commit -m "feat(cctv): skip re-recognition of handled students via period tracks"
```

---

### Task 3: Verification

**Files:** none (no code changes)

- [ ] **Step 1: Run the full CCTV test suite**

Run (from `backend/`):

```powershell
python test_cctv_service.py
```

Expected: `All CCTV service tests passed`.

- [ ] **Step 2: Restart the backend and smoke-check**

Kill the running uvicorn (find it first):

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "uvicorn app.main" } | Select-Object ProcessId
Stop-Process -Id <PID> -Force
```

Restart from `backend/` with logging (adjust python path as needed):

```powershell
Start-Process -FilePath "C:\Users\Ripple\AppData\Local\Programs\Python\Python312\python.exe" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory "D:\Misc\github repo test\V4\backend" -RedirectStandardOutput "$env:TEMP\opencode\uvicorn_cctv2.log" -RedirectStandardError "$env:TEMP\opencode\uvicorn_cctv2.err.log" -WindowStyle Hidden
Start-Sleep -Seconds 8
```

Login and check status + events:

```powershell
$login = Invoke-RestMethod -Uri "http://127.0.0.1:8000/login" -Method Post -Body (@{ email = "admin@test.com"; password = "admin123" } | ConvertTo-Json) -ContentType "application/json"
$h = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/cctv/status" -Headers $h | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "http://127.0.0.1:8000/cctv/events?limit=50" -Headers $h | ConvertTo-Json -Compress
```

Expected: status returns the usual fields; events returns the recent feed (empty or short list). If a real camera is available, watch `/cctv/events` during a class period and confirm each recognized student appears at most once per period (no repeating `skipped` entries) while the service keeps logging unrecognized/spoof entries each capture.

- [ ] **Step 3: Check git is clean**

```powershell
git status
```

Expected: working tree clean (only the committed plan/spec docs and the two commits from Task 1 + Task 2).
