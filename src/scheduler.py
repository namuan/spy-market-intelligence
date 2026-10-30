from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline import run_daily_update


def main() -> None:
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_daily_update,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30, timezone="America/New_York"),
        id="daily-market-update",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=7200,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
