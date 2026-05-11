import asyncio
import json
import logging
import os
from twikit import Client
from src import config, db

logger = logging.getLogger(__name__)

_client: Client | None = None


async def _get_client() -> Client:
    global _client
    if _client is not None:
        return _client

    client = Client(language="en-US")

    if os.path.exists(config.SESSION_FILE):
        try:
            client.load_cookies(config.SESSION_FILE)
            logger.info("Loaded Twitter session from %s", config.SESSION_FILE)
            _client = client
            return _client
        except Exception as e:
            logger.warning("Failed to load cookies (%s), falling back to login", e)

    await client.login(
        auth_info_1=config.TWITTER_USERNAME,
        auth_info_2=config.TWITTER_EMAIL,
        password=config.TWITTER_PASSWORD,
    )
    client.save_cookies(config.SESSION_FILE)
    logger.info("Logged in to Twitter and saved session to %s", config.SESSION_FILE)
    _client = client
    return _client


async def _login_fresh() -> Client:
    global _client
    _client = None
    if os.path.exists(config.SESSION_FILE):
        try:
            os.remove(config.SESSION_FILE)
        except OSError:
            pass
    return await _get_client()


def _tweet_url(handle: str, tweet_id: str) -> str:
    return f"https://x.com/{handle}/status/{tweet_id}"


async def fetch_account(handle: str) -> int:
    try:
        client = await _get_client()
        user = await client.get_user_by_screen_name(handle)
        tweets = await user.get_tweets("Tweets", count=config.MAX_TWEETS_PER_FETCH)
    except Exception as e:
        if any(kw in str(e).lower() for kw in ("cookie", "auth", "session", "key_byte", "indices")):
            logger.warning("Session error for @%s, retrying with fresh login: %s", handle, e)
            try:
                client = await _login_fresh()
                user = await client.get_user_by_screen_name(handle)
                tweets = await user.get_tweets("Tweets", count=config.MAX_TWEETS_PER_FETCH)
            except Exception as e2:
                logger.error("Fetch failed for @%s after re-login: %s", handle, e2)
                return 0
        else:
            logger.error("Fetch failed for @%s: %s", handle, e)
            return 0

    inserted = 0
    for tweet in tweets:
        stored = await db.insert_tweet(
            tweet_id=tweet.id,
            author_handle=handle,
            text=tweet.text,
            created_at=str(tweet.created_at),
            url=_tweet_url(handle, tweet.id),
        )
        if stored:
            inserted += 1

    logger.info("@%s: fetched %d tweets, %d new", handle, len(tweets), inserted)
    return inserted


async def fetch_all_accounts() -> None:
    logger.info("Starting fetch for %d accounts", len(config.ACCOUNTS))
    for handle in config.ACCOUNTS:
        await fetch_account(handle)
        await asyncio.sleep(2)
