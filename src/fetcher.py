import asyncio
import json
import logging
import os
from twikit import Client
from twikit.user import User
from twikit.x_client_transaction.transaction import ClientTransaction
from src import config, db

logger = logging.getLogger(__name__)

# twikit's JS-parsing for x-client-transaction-id is broken on Twitter's
# current frontend (ondemand.s bundle no longer exists). Patch it to be
# a no-op so fetches proceed using cookie auth without the header.
async def _noop_transaction_init(self, session, headers):
    self.home_page_response = None
    self.DEFAULT_ROW_INDEX = 0
    self.DEFAULT_KEY_BYTES_INDICES = []
    self.key = "noop"
    self.key_bytes = [0] * 64
    self.animation_key = "noop"

def _noop_generate_transaction_id(self, method, path, **kwargs):
    return ""

ClientTransaction.init = _noop_transaction_init
ClientTransaction.generate_transaction_id = _noop_generate_transaction_id

# twikit User.__init__ uses hard key access on legacy fields that Twitter
# omits for some accounts. Patch __init__ to use .get() throughout.
_orig_user_init = User.__init__

def _safe_user_init(self, client, data):
    legacy = data['legacy']
    self._client = client
    self.id = data['rest_id']
    self.created_at = legacy.get('created_at')
    self.name = legacy.get('name')
    self.screen_name = legacy.get('screen_name')
    self.profile_image_url = legacy.get('profile_image_url_https')
    self.profile_banner_url = legacy.get('profile_banner_url')
    self.url = legacy.get('url')
    self.location = legacy.get('location')
    self.description = legacy.get('description')
    self.description_urls = legacy.get('entities', {}).get('description', {}).get('urls', [])
    self.urls = legacy.get('entities', {}).get('url', {}).get('urls')
    self.pinned_tweet_ids = legacy.get('pinned_tweet_ids_str', [])
    self.is_blue_verified = data.get('is_blue_verified', False)
    self.verified = legacy.get('verified', False)
    self.possibly_sensitive = legacy.get('possibly_sensitive', False)
    self.can_dm = legacy.get('can_dm', False)
    self.can_media_tag = legacy.get('can_media_tag', False)
    self.want_retweets = legacy.get('want_retweets', False)
    self.default_profile = legacy.get('default_profile', False)
    self.default_profile_image = legacy.get('default_profile_image', False)
    self.has_custom_timelines = legacy.get('has_custom_timelines', False)
    self.followers_count = legacy.get('followers_count', 0)
    self.fast_followers_count = legacy.get('fast_followers_count', 0)
    self.normal_followers_count = legacy.get('normal_followers_count', 0)
    self.following_count = legacy.get('friends_count', 0)
    self.favourites_count = legacy.get('favourites_count', 0)
    self.listed_count = legacy.get('listed_count', 0)
    self.media_count = legacy.get('media_count', 0)
    self.statuses_count = legacy.get('statuses_count', 0)
    self.is_translator = legacy.get('is_translator', False)
    self.translator_type = legacy.get('translator_type')
    self.withheld_in_countries = legacy.get('withheld_in_countries', [])
    self.protected = legacy.get('protected', False)

User.__init__ = _safe_user_init

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
        if any(kw in str(e).lower() for kw in ("cookie", "auth", "session")):
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
