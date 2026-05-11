import asyncio
import logging
import signal
from src import db, fetcher, scheduler as scheduler_mod, telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await db.init_db()
    logger.info("Database initialised")

    await fetcher.fetch_all_accounts()
    logger.info("Initial fetch complete")

    app = telegram_bot.build_application()
    scheduler = scheduler_mod.build_scheduler(app)
    scheduler.start()
    logger.info("Scheduler started")

    loop = asyncio.get_running_loop()

    def _shutdown(signum, frame):
        logger.info("Received signal %s, shutting down", signum)
        scheduler.shutdown(wait=False)
        loop.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Starting Telegram bot polling")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Feed Harvester running — press Ctrl+C to stop")
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
