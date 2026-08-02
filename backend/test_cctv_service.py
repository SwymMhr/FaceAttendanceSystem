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


def test_stream_urls_fallback_order():
    """The primary URL comes first, followed by each fallback URL in order."""
    from app.services.cctv_service import stream_urls
    urls = stream_urls()
    assert len(urls) == 3, f"expected primary + 2 fallbacks, got {urls}"
    assert "video3" in urls[0], "primary URL should be video3"
    assert "video2" in urls[1], "first fallback should be video2"
    assert "video1" in urls[2], "second fallback should be video1"


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


def test_update_settings_partial_validation():
    """A partial update must not create an inverted interval window."""
    from app.services.cctv_service import CCTVService
    svc = CCTVService()
    svc.update_settings(capture_min=1.0, capture_max=5.0)
    try:
        svc.update_settings(capture_min=7.0)
        raise AssertionError("expected ValueError for partial min > stored max")
    except ValueError:
        pass
    try:
        svc.update_settings(capture_max=0.5)
        raise AssertionError("expected ValueError for partial max < stored min")
    except ValueError:
        pass


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


def test_attendance_capture_does_not_handle_unrecognized():
    """An unrecognized/spoof person (db_id None) is not marked handled, so
    they keep being retried on later captures."""
    import time
    from unittest.mock import patch
    import numpy as np
    from app.services.cctv_service import CCTVService
    svc = CCTVService()
    svc._handled_students = set()
    svc._tracks = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch("app.services.cctv_service.detect_persons", return_value=[(0, 0, 20, 60)]), \
         patch.object(svc, "_attendance_recognize_person", return_value=("Unknown", 0.7, "unrecognized", "not recognized", (0, 165, 255), None)) as arp, \
         patch.object(svc, "_log_event") as le:
        svc._run_attendance_capture(frame)
    arp.assert_called_once()
    le.assert_called_once()
    assert svc._handled_students == set()
    assert svc._tracks[0]["student_id"] is None


if __name__ == "__main__":
    test_head_region()
    test_detect_persons_empty_frame()
    test_stream_urls_fallback_order()
    test_validate_interval()
    test_random_capture_delay()
    test_should_capture()
    test_toggle_defaults()
    test_update_settings()
    test_update_settings_partial_validation()
    test_iou()
    test_match_tracks()
    test_prune_tracks()
    test_is_handled()
    test_attendance_capture_skips_handled_student()
    test_attendance_capture_processes_new_student()
    test_period_start_clears_tracking_state()
    test_attendance_capture_does_not_handle_unrecognized()
    print("All CCTV service tests passed")
