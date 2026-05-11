import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from src import config, db, digest as digest_mod

logger = logging.getLogger(__name__)


def _auth(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.id == config.TELEGRAM_CHAT_ID


async def send_chunks(app: Application, chunks: list[str]) -> bool:
    try:
        for chunk in chunks:
            await app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=chunk)
        return True
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


async def deliver_digest(app: Application) -> None:
    chunks, tweet_ids = await digest_mod.run_digest()
    if not chunks:
        logger.warning("Digest produced no output; skipping delivery")
        return

    ok = await send_chunks(app, chunks)
    if ok and tweet_ids:
        await db.mark_digested(tweet_ids)
        logger.info("Digest delivered and %d tweets marked as seen", len(tweet_ids))
    elif not ok:
        logger.warning("Telegram delivery failed; tweets NOT marked as seen (will retry)")


async def cmd_digest_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    await update.message.reply_text("Running digest...")
    await deliver_digest(context.application)


async def cmd_expand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /expand <handle>")
        return
    handle = context.args[0].lstrip("@")
    tweets = await db.get_unseen_by_handle(handle)
    if not tweets:
        await update.message.reply_text(f"No unseen tweets for @{handle}.")
        return
    await update.message.reply_text(f"Generating deep-dive for @{handle}...")
    summary = await digest_mod.summarize_handle(handle, tweets)
    if summary:
        await update.message.reply_text(summary)
    else:
        await update.message.reply_text("Summarization failed.")


async def cmd_raw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /raw <handle>")
        return
    handle = context.args[0].lstrip("@")
    tweets = await db.get_unseen_by_handle(handle)
    if not tweets:
        await update.message.reply_text(f"No unseen tweets for @{handle}.")
        return
    lines = [f"[{t['created_at']}]\n{t['text']}" for t in tweets]
    text = "\n\n---\n\n".join(lines)
    for i in range(0, len(text), digest_mod.TELEGRAM_LIMIT):
        await update.message.reply_text(text[i:i + digest_mod.TELEGRAM_LIMIT])


async def cmd_since(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /since <handle> <Nd>  e.g. /since karpathy 3d")
        return
    handle = context.args[0].lstrip("@")
    raw_days = context.args[1].rstrip("dD")
    try:
        days = int(raw_days)
    except ValueError:
        await update.message.reply_text("Days must be a number, e.g. 3d")
        return
    tweets = await db.get_tweets_since(handle, days)
    if not tweets:
        await update.message.reply_text(f"No tweets for @{handle} in the last {days} day(s).")
        return
    lines = [f"[{t['created_at']}]\n{t['text']}" for t in tweets]
    text = f"@{handle} — last {days}d ({len(tweets)} tweets)\n\n" + "\n\n---\n\n".join(lines)
    for i in range(0, len(text), digest_mod.TELEGRAM_LIMIT):
        await update.message.reply_text(text[i:i + digest_mod.TELEGRAM_LIMIT])


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    counts = await db.get_unseen_counts()
    if not counts:
        await update.message.reply_text("No unseen tweets.")
        return
    lines = [f"@{handle}: {n} unseen" for handle, n in sorted(counts.items())]
    await update.message.reply_text("\n".join(lines))


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("digest", cmd_digest_now))
    app.add_handler(CommandHandler("expand", cmd_expand))
    app.add_handler(CommandHandler("raw", cmd_raw))
    app.add_handler(CommandHandler("since", cmd_since))
    app.add_handler(CommandHandler("status", cmd_status))
    return app
