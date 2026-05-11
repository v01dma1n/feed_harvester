import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src import config, fetcher, telegram_bot

logger = logging.getLogger(__name__)


def build_scheduler(app) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        fetcher.fetch_all_accounts,
        trigger="interval",
        minutes=config.FETCH_INTERVAL_MINUTES,
        jitter=config.FETCH_INTERVAL_JITTER_MINUTES * 60,
        id="fetch_job",
        name="Tweet fetch",
        max_instances=1,
    )

    scheduler.add_job(
        telegram_bot.deliver_digest,
        trigger="cron",
        hour=config.DIGEST_HOUR,
        minute=0,
        id="digest_job",
        name="Daily digest",
        max_instances=1,
        args=[app],
    )

    return scheduler
