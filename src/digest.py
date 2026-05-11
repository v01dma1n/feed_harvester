import logging
from google import genai
from google.genai import types
from src import config, db

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=config.GEMINI_API_KEY)

_SYSTEM_INSTRUCTION = (
    "You are a concise news assistant summarizing Twitter activity for a technical reader. "
    "For each account, write 2-4 sentences covering the main themes and notable posts. "
    "Use plain text. No markdown. No bullet points. Keep each account summary under 100 words."
)

TELEGRAM_LIMIT = 4096


def _build_prompt(tweets_by_handle: dict[str, list[dict]]) -> str:
    lines = ["Summarize the following tweets from the last 24 hours, grouped by account.\n"]
    for handle, tweets in tweets_by_handle.items():
        lines.append(f"[{handle}]")
        for t in tweets:
            lines.append(t["text"])
        lines.append("")
    return "\n".join(lines)


def _group_by_handle(tweets: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for t in tweets:
        grouped.setdefault(t["author_handle"], []).append(t)
    return grouped


async def summarize(tweets: list[dict]) -> str | None:
    if not tweets:
        return None
    grouped = _group_by_handle(tweets)
    prompt = _build_prompt(grouped)
    try:
        response = await _client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=_SYSTEM_INSTRUCTION),
        )
        return response.text.strip()
    except Exception as e:
        logger.error("Gemini summarization failed: %s", e)
        return None


async def summarize_handle(handle: str, tweets: list[dict]) -> str | None:
    if not tweets:
        return None
    grouped = {handle: tweets}
    prompt = _build_prompt(grouped)
    try:
        response = await _client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=_SYSTEM_INSTRUCTION),
        )
        return response.text.strip()
    except Exception as e:
        logger.error("Gemini expand failed for @%s: %s", handle, e)
        return None


def split_for_telegram(text: str, tweets_by_handle: dict[str, list[dict]]) -> list[str]:
    """Split digest text into <=4096-char chunks, never splitting mid-account."""
    if len(text) <= TELEGRAM_LIMIT:
        return [text]

    # Try to split on account-level paragraphs (double newline separated)
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= TELEGRAM_LIMIT:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text[:TELEGRAM_LIMIT]]


async def run_digest() -> tuple[list[str], list[str]]:
    """Returns (message_chunks, tweet_ids_included)."""
    tweets = await db.get_unseen_tweets()
    if not tweets:
        return ["No new tweets since the last digest."], []

    summary = await summarize(tweets)
    if summary is None:
        return [], []

    grouped = _group_by_handle(tweets)
    chunks = split_for_telegram(summary, grouped)
    ids = [t["tweet_id"] for t in tweets]
    return chunks, ids
