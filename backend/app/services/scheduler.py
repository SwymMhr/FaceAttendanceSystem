# app/services/scheduler.py
# Runs every 5 minutes: finds any period whose end_time has already
# passed today and finalizes absentees for it. finalize_period_absentees()
# is idempotent, so re-checking an already-finalized period is harmless.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.database import SessionLocal
from app.models.db_models import Period, PeriodSlot
from app.services.absence_service import finalize_period_absentees

LOCAL_TZ = ZoneInfo("Asia/Kathmandu")
_WEEKDAY_MAP = {6: "SUNDAY", 0: "MONDAY", 1: "TUESDAY", 2: "WEDNESDAY", 3: "THURSDAY"}


def _run_absence_check():
    db = SessionLocal()
    try:
        now_local = datetime.now(timezone.utc).astimezone(LOCAL_TZ)
        day = _WEEKDAY_MAP.get(now_local.weekday())
        if day is None:
            return  # Friday/Saturday — nothing scheduled

        current_time = now_local.time()

        ended_periods = (
            db.query(Period)
              .join(PeriodSlot, Period.period_number == PeriodSlot.period_number)
              .filter(Period.day_of_week == day, PeriodSlot.end_time <= current_time)
              .all()
        )

        for period in ended_periods:
            try:
                result = finalize_period_absentees(db, period.id)
                if result["newly_marked_absent"]:
                    print(f"[scheduler] Period {period.id}: marked absent {result['newly_marked_absent']}")
            except Exception as e:
                print(f"[scheduler] Error finalizing period {period.id}: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_run_absence_check, "interval", minutes=5, id="absence_check")
    scheduler.start()
    print("[scheduler] Absence-check background job started (every 5 min).")
    return scheduler