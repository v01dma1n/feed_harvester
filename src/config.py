import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

app_env = os.environ.get("APP_ENV", "DEV").upper()
if app_env == "DEV":
    RUN_MODE = "DEV"
    _env_file = ".feed_harvester_dev.env"
else:
    RUN_MODE = "PROD"
    _env_file = ".feed_harvester.env"

_env_path = Path.home() / _env_file
load_dotenv(_env_path)
logger.info("Running in %s mode, config from %s", RUN_MODE, _env_path)

def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

TWITTER_USERNAME = _require("TWITTER_USERNAME")
TWITTER_EMAIL = _require("TWITTER_EMAIL")
TWITTER_PASSWORD = _require("TWITTER_PASSWORD")

GEMINI_API_KEY = _require("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(_require("TELEGRAM_CHAT_ID"))

DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "8"))
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", "30"))
FETCH_INTERVAL_JITTER_MINUTES = int(os.getenv("FETCH_INTERVAL_JITTER_MINUTES", "5"))
MAX_TWEETS_PER_FETCH = int(os.getenv("MAX_TWEETS_PER_FETCH", "20"))
MIN_TWEETS_PER_FETCH = int(os.getenv("MIN_TWEETS_PER_FETCH", "15"))
QUIET_HOUR_START = int(os.getenv("QUIET_HOUR_START", "1"))
QUIET_HOUR_END = int(os.getenv("QUIET_HOUR_END", "6"))

ACCOUNTS: list[str] = [
    a.strip() for a in os.getenv("ACCOUNTS", "karpathy,edzitron,raydalio,dhh").split(",") if a.strip()
]

SESSION_FILE = os.getenv("SESSION_FILE", "twitter_session.json")
DB_FILE = os.getenv("DB_FILE", str(Path.home() / "bin" / "db" / "feed_harvester.db"))
