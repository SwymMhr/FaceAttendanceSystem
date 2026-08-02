# CCTV Skip Re-Recognition of Handled Students Design — V4

Date: 2026-08-02

Status: Approved (2026-08-02)

## Goal

Stop auto-capture from re-running the full recognition pipeline on students
whose attendance is already recorded for the current class period, and stop the
"Recent Recognitions" event list from piling up `skipped` entries for the same
student every capture.

Today every auto-capture (randomly every 1–5s during a period) detects all
persons and, for each, runs liveness (MiniFASNet) + recognition (ArcFace) +
`mark_attendance_logic`, then logs an event. `mark_attendance_logic` returns
`skipped` for a student who already has an attendance row this period, so the
same recognized student produces a fresh `skipped` event every capture — wasting
CPU on expensive CNNs and flooding the event feed.

## Requirements

- **Once per period**: a student whose attendance was recorded this period is
  **not recognized again** — liveness, recognition, marking, and event logging
  are all skipped for them on subsequent captures.
- **Events logged once per student per period** (the real `pending` /
  `already marked` outcome), not repeated every capture.
- **Unrecognized / spoof-detected people are NOT skipped** — they keep being
  re-attempted and logged every capture (angle may improve; spoof attempts stay
  flagged).
- **Resets each period**: the skip state clears when a new class period starts,
  so the student is recognized and marked fresh for the next period.
- **Lightweight person tracking**: associate the same person across captures via
  IoU (no new model). A different person standing in the same spot must NOT be
  wrongly skipped.
- No change to the live display path, `mark_attendance_logic`, the frontend, or
  the event-list UI.

## Architecture

Add worker-private track state to `CCTVService`. Only the worker thread's
auto-capture path touches it, so no lock is needed:

```
auto-capture (worker thread, every 1–5s)
        │
        ▼
 detect_persons(frame)
        │
        ▼
 prune stale tracks ──► match boxes to tracks (IoU + area ratio)
        │                       │
        │                       ├─ handled student  ──► SKIP pipeline (box refresh only)
        │                       ├─ new / unmatched   ──► full pipeline → assign student_id
        │                       └─ re-matched track  ──► reuse student_id → skip if handled
        ▼
 log event ONLY on first handling / on unrecognized / on spoof
```

## Components

### Backend — `app/services/cctv_service.py`

New constants:

- `IOU_MATCH_THRESHOLD: float = 0.4` — minimum IoU to match a box to a track.
- `MAX_AREA_RATIO: float = 2.0` — box area ratio limit; prevents a different
  person in the same spot being matched to a handled track.
- `TRACK_TTL: float = 30.0` — a track not seen for this long is pruned.

New worker-private state (accessed only by the worker thread's auto-capture
path):

- `_tracks: list[dict]` — each `{box: (x1,y1,x2,y2), student_id: int|None,
  last_seen: float}`. Boxes in original frame coordinates (post `inv_scale`).
- `_handled_students: set[int]` — student IDs whose attendance was recorded
  this period.

Pure, unit-testable helpers (module level):

- `iou(box_a, box_b) -> float` — intersection over union.
- `match_tracks(boxes, tracks, iou_threshold, max_area_ratio) ->
  list[track_index|None]` — greedy one-to-one matching: for each box pick the
  best track with IoU ≥ threshold AND area ratio within limit; each track used
  at most once.
- `prune_tracks(tracks, now, ttl) -> list` — drop tracks with
  `now - last_seen > ttl`.
- `is_handled(track, handled_students) -> bool` — `track["student_id"] is not
  None and track["student_id"] in handled_students`. Single source of truth for
  the skip decision so it can be unit-tested without running the CNN pipeline.

Rework `_run_attendance_capture(frame)`:

1. `detect_persons` → `boxes` (existing).
2. `tracks = prune_tracks(self._tracks, now, TRACK_TTL)`.
3. `matches = match_tracks(boxes, tracks, IOU_MATCH_THRESHOLD, MAX_AREA_RATIO)`.
4. For each box with its matched track (or a new track):
   - Update `box` + `last_seen`.
   - If `is_handled(track, self._handled_students)`: **skip** — no liveness,
     no identify, no `mark_attendance_logic`, no event.
   - Else run the existing `_attendance_recognize_person` pipeline:
     - Known student (`status` in `pending`, `skipped`, `error`): set
       `track["student_id"]`, add to `self._handled_students`, log the event
       (once per period).
     - `unrecognized` or `rejected` (spoof): leave unhandled, log the event
       (kept retrying).
5. `self._tracks = tracks`.

Reset:

- In `_refresh_period_state`, when `in_period` transitions **false → true**
  (period start): clear `self._tracks` and `self._handled_students`.
- Also clear both in `start()` for a fresh service run.

## Data Flow

1. First capture of a period: every person is new → full pipeline runs.
   Recognized student → attendance recorded → student added to
   `_handled_students` → one event (`pending` or `already marked`) logged.
2. Later captures: the person's box matches their track → skip. No event.
3. Student leaves frame and returns within TTL → still matched → still skipped.
   Returns after TTL → new track → re-recognized → `mark_attendance_logic`
   returns `skipped` → one event logged, added to handled set again.
4. Next period starts → state clears → student recognized and marked fresh.

## Error Handling

- A stale/malformed track never breaks the capture: matching falls back to
  treating the box as new.
- Worker iteration try/except unchanged (existing crash protection).
- If `mark_attendance_logic` returns `error` (unexpected), the student is still
  added to `_handled_students` so the error is logged once, not spammed.

## Testing

`backend/test_cctv_service.py` — add:

- `iou`: overlapping / identical / disjoint boxes.
- `match_tracks`: matches overlapping boxes, rejects disjoint and
  area-ratio-violating boxes, one-to-one greedy (two boxes matching one track
  only binds once).
- `prune_tracks`: drops old tracks, keeps fresh ones.
- `is_handled`: a track whose `student_id` is in `_handled_students` is skipped;
  a track with `student_id=None` (unrecognized/spoof) is not.
- Period reset: `_handled_students`/`_tracks` cleared on false→true period
  transition (via `_refresh_period_state` with mocked `get_current_period`).

Manual E2E (running servers): during a period, watch `/cctv/events` — each
recognized student appears once (not once per capture); unknown/spoof people
keep appearing every capture; a new period re-logs the student.

## Out of Scope (future)

- Appearance-based re-identification (this design uses IoU only, which is
  sufficient for a fixed classroom camera).
- Suppressing unrecognized/spoof events (user chose to keep retrying them).
- Sharing track state with the live display path.
