"""
RQ Scheduler — sets up the daily monitoring cron for all active themes.
Run once on worker startup or via management command.
"""
import logging

import redis
from rq_scheduler import Scheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.theme import Theme
from app.services.auto_discovery import run_auto_discovery
from app.services.pipeline import run_monitoring_pipeline

logger = logging.getLogger(__name__)

DAILY_JOB_ID_PREFIX = "daily-pipeline-"
WEEKLY_DISCOVERY_JOB_ID_PREFIX = "weekly-discovery-"


def setup_daily_schedules():
    """
    Register a daily cron job for each active theme (pipeline)
    and a weekly cron job for automated source discovery.
    Safe to call repeatedly — existing jobs are replaced.
    """
    r = redis.from_url(settings.REDIS_URL)
    scheduler = Scheduler(queue_name="fem-jobs", connection=r)
    db = SessionLocal()

    try:
        active_themes = db.query(Theme).filter(Theme.status == "active").all()

        # Cancel stale jobs for themes no longer active
        existing_jobs = {job.id: job for job in scheduler.get_jobs()}
        active_theme_ids = {str(t.id) for t in active_themes}
        for job_id, job in existing_jobs.items():
            prefix_match = (
                job_id.startswith(DAILY_JOB_ID_PREFIX) or
                job_id.startswith(WEEKLY_DISCOVERY_JOB_ID_PREFIX)
            )
            if prefix_match:
                if job_id.startswith(DAILY_JOB_ID_PREFIX):
                    tid = job_id[len(DAILY_JOB_ID_PREFIX):]
                else:
                    tid = job_id[len(WEEKLY_DISCOVERY_JOB_ID_PREFIX):]
                if tid not in active_theme_ids:
                    scheduler.cancel(job)
                    logger.info("Cancelled stale schedule for theme %s", tid)

        for theme in active_themes:
            theme_id_str = str(theme.id)

            # Daily pipeline job
            pipeline_job_id = f"{DAILY_JOB_ID_PREFIX}{theme_id_str}"
            if pipeline_job_id in existing_jobs:
                scheduler.cancel(existing_jobs[pipeline_job_id])
            scheduler.cron(
                "0 6 * * *",  # 06:00 UTC daily
                func=run_monitoring_pipeline,
                args=[theme_id_str],
                id=pipeline_job_id,
                queue_name="fem-jobs",
                use_local_timezone=False,
            )
            logger.info("Scheduled daily pipeline for theme: %s", theme.name)

            # Weekly source discovery job
            discovery_job_id = f"{WEEKLY_DISCOVERY_JOB_ID_PREFIX}{theme_id_str}"
            if discovery_job_id in existing_jobs:
                scheduler.cancel(existing_jobs[discovery_job_id])
            scheduler.cron(
                "0 3 * * 0",  # 03:00 UTC every Sunday
                func=run_auto_discovery,
                args=[theme_id_str],
                id=discovery_job_id,
                queue_name="fem-jobs",
                use_local_timezone=False,
            )
            logger.info("Scheduled weekly discovery for theme: %s", theme.name)

        logger.info("Scheduler setup complete — %d active themes", len(active_themes))
    finally:
        db.close()
