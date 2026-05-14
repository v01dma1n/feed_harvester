import logging
import aiosqlite
from datetime import datetime, timezone
from src import config

logger = logging.getLogger(__name__)

CREATE_TWEETS = """
CREATE TABLE IF NOT EXISTS tweets (
    tweet_id     TEXT PRIMARY KEY,
    author_handle TEXT NOT NULL,
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    url          TEXT,
    fetched_at   TEXT NOT NULL,
    digested_at  TEXT
);
"""
CREATE_IDX_AUTHOR = "CREATE INDEX IF NOT EXISTS idx_author ON tweets(author_handle);"
CREATE_IDX_DIGESTED = "CREATE INDEX IF NOT EXISTS idx_digested ON tweets(digested_at);"


async def _migrate_created_at(conn: aiosqlite.Connection) -> None:
    async with conn.execute("SELECT tweet_id, created_at FROM tweets") as cur:
        rows = await cur.fetchall()
    updated = 0
    for tweet_id, created_at in rows:
        if not created_at or created_at[0].isdigit():
            continue  # already ISO 8601
        try:
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            iso = dt.astimezone(timezone.utc).isoformat()
            await conn.execute("UPDATE tweets SET created_at = ? WHERE tweet_id = ?", (iso, tweet_id))
            updated += 1
        except ValueError:
            pass
    if updated:
        await conn.commit()
        logger.info("Migrated %d created_at values to ISO 8601", updated)


async def init_db() -> None:
    async with aiosqlite.connect(config.DB_FILE) as db:
        await db.execute(CREATE_TWEETS)
        await db.execute(CREATE_IDX_AUTHOR)
        await db.execute(CREATE_IDX_DIGESTED)
        await db.commit()
        await _migrate_created_at(db)


async def insert_tweet(tweet_id: str, author_handle: str, text: str,
                       created_at: str, url: str | None) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(config.DB_FILE) as db:
        try:
            await db.execute(
                "INSERT INTO tweets (tweet_id, author_handle, text, created_at, url, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tweet_id, author_handle, text, created_at, url, now),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_unseen_tweets() -> list[dict]:
    async with aiosqlite.connect(config.DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tweets WHERE digested_at IS NULL ORDER BY author_handle, created_at"
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_unseen_by_handle(handle: str) -> list[dict]:
    async with aiosqlite.connect(config.DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tweets WHERE digested_at IS NULL AND author_handle = ? ORDER BY created_at",
            (handle,),
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_tweets_since(handle: str, days: int) -> list[dict]:
    async with aiosqlite.connect(config.DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tweets WHERE author_handle = ? "
            "AND created_at >= datetime('now', ? || ' days') ORDER BY created_at",
            (handle, f"-{days}"),
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def mark_digested(tweet_ids: list[str]) -> None:
    if not tweet_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" * len(tweet_ids))
    async with aiosqlite.connect(config.DB_FILE) as db:
        await db.execute(
            f"UPDATE tweets SET digested_at = ? WHERE tweet_id IN ({placeholders})",
            [now, *tweet_ids],
        )
        await db.commit()


async def get_unseen_counts() -> dict[str, int]:
    async with aiosqlite.connect(config.DB_FILE) as db:
        async with db.execute(
            "SELECT author_handle, COUNT(*) FROM tweets WHERE digested_at IS NULL GROUP BY author_handle"
        ) as cur:
            return {row[0]: row[1] for row in await cur.fetchall()}
