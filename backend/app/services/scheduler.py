# app/services/scheduler.py
# Runs every 5 minutes but only actually does anything once the school day
# is over (i.e. once the last period slot's end_time has passed). This
# gives teachers the whole day to review pending detections and mark
# attendance themselves. Anything a teacher hasn't touched by then gets
# auto-finalized: lingering "pending" detections become "present", and
# anyone with no row at all becomes "absent" (see absence_service.py).
# finalize_period_absentees() is idempotent, so re-checking an
# already-finalized period is harmless — the daily guard below just
# avoids doing the same query on every single tick after day-end.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.database import SessionLocal
from app.models.db_models import Period, PeriodSlot
from app.services.absence_service import finalize_period_absentees

LOCAL_TZ = ZoneInfo("Asia/Kathmandu")
_WEEKDAY_MAP = {6: "SUNDAY", 0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY"}

# Tracks the local date this job last ran an end-of-day finalize for, so we
# don't re-run the same query every 5 minutes for the rest of the evening.
_last_finalized_date = None


def _run_end_of_day_finalize():
    global _last_finalized_date
    db = SessionLocal()
    try:
        now_local = datetime.now(timezone.utc).astimezone(LOCAL_TZ)
        today = now_local.date()
        if _last_finalized_date == today:
            return  # already ran the end-of-day sweep for today

        day = _WEEKDAY_MAP.get(now_local.weekday())
        if day is None:
            return  # Friday/Saturday — nothing scheduled

        current_time = now_local.time()

        day_end = db.query(PeriodSlot).order_by(PeriodSlot.end_time.desc()).first()
        if not day_end or current_time < day_end.end_time:
            return  # school day isn't over yet — leave attendance for teachers to review

        todays_periods = db.query(Period).filter(Period.day_of_week == day).all()

        for period in todays_periods:
            try:
                result = finalize_period_absentees(db, period.id)
                if result["auto_confirmed_present"]:
                    print(f"[scheduler] Period {period.id}: auto-confirmed present {result['auto_confirmed_present']}")
                if result["newly_marked_absent"]:
                    print(f"[scheduler] Period {period.id}: marked absent {result['newly_marked_absent']}")
            except Exception as e:
                print(f"[scheduler] Error finalizing period {period.id}: {e}")

        _last_finalized_date = today
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_run_end_of_day_finalize, "interval", minutes=5, id="end_of_day_finalize")
    scheduler.start()
    print("[scheduler] End-of-day auto-finalize job started (checks every 5 min, acts once/day).")
    return scheduler