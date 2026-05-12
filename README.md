# Feed Harvester

A local Python daemon that monitors a fixed set of Twitter/X accounts, stores tweets in a SQLite database, and delivers a daily AI-generated digest via Telegram.

## What it does

- Fetches 15–20 recent tweets per account every ~30 minutes (±5 min jitter) via [twikit](https://github.com/d60/twikit)
- Deduplicates by tweet ID and stores unseen tweets in SQLite
- Skips fetching during quiet hours (01:00–06:00 by default)
- At 08:00 local time, sends a Gemini-summarized digest to Telegram
- Exposes a Telegram bot for on-demand queries

## Accounts monitored

| Handle | Topic |
|---|---|
| @karpathy | AI/ML research |
| @edzitron | Tech criticism |
| @raydalio | Macro finance |
| @dhh | Software development / Rails |

Configurable via the `ACCOUNTS` env var.

## Requirements

- Python 3.11+ (ml-env pyenv environment)
- A Twitter/X account with a valid browser session
- A Telegram bot token and chat ID
- A Google Gemini API key

## Project structure

```
feed-harvester/
├── .env.example                  # env var template
├── .gitignore
├── requirements.txt
├── db/                           # DEV database (gitignored)
├── log/                          # log dir placeholder
├── scripts/
│   └── deploy.sh                 # deploy source → ~/bin/feed_harvester
├── systemd/
│   └── feed-harvester.service    # systemd user unit
└── src/
    ├── main.py                   # entry point, scheduler setup
    ├── config.py                 # env loading, DEV/PROD selection
    ├── fetcher.py                # twikit client, fetch logic
    ├── db.py                     # SQLite schema and queries
    ├── digest.py                 # Gemini summarization
    ├── telegram_bot.py           # bot commands and digest delivery
    └── scheduler.py              # APScheduler job definitions
```

**Source:** `~/projects/OpenSource/feed_harvester/`
**Production runtime:** `~/bin/feed_harvester/`

## Database locations

| Environment | Path |
|---|---|
| DEV | `~/projects/OpenSource/feed_harvester/db/feed_harvester.db` |
| PROD | `~/bin/db/feed_harvester.db` |

Both are gitignored.

## Setup

### 1. Configure environment

```bash
cp .env.example ~/.feed_harvester.env
cp .env.example ~/.feed_harvester_dev.env
# Edit both files with your credentials
```

Required variables:

```
TWITTER_USERNAME=
TWITTER_EMAIL=
TWITTER_PASSWORD=
GEMINI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### 2. Seed the Twitter session

The server IP is blocked by Cloudflare from Twitter's login endpoint. You must seed the session manually from a browser:

1. Log into x.com in your browser
2. Open DevTools → Application → Cookies → `https://x.com`
3. Copy the values of `auth_token` and `ct0`
4. Create the session file on the server:

```bash
cat > ~/bin/feed_harvester/twitter_session.json << 'EOF'
{
  "auth_token": "YOUR_AUTH_TOKEN",
  "ct0": "YOUR_CT0"
}
EOF
```

The session file is gitignored and never committed. Username/password in `.env` are only used as a fallback if the session file is missing or expired. Sessions typically last 7–30 days.

### 3. Deploy and start

```bash
bash scripts/deploy.sh

# First-time enable:
systemctl --user enable feed-harvester
```

## Development vs production

The `APP_ENV` environment variable controls which secrets file and database are used:

| APP_ENV | Secrets file | Database |
|---|---|---|
| `DEV` (default) | `~/.feed_harvester_dev.env` | `<project>/db/feed_harvester.db` |
| `PROD` | `~/.feed_harvester.env` | `~/bin/db/feed_harvester.db` |

The systemd unit sets `APP_ENV=PROD`. Running manually from the terminal uses DEV mode.

```bash
# Run manually in DEV mode
cd ~/projects/OpenSource/feed_harvester
~/.pyenv/versions/ml-env/bin/python -m src.main

# Run manually in PROD mode
APP_ENV=PROD ~/.pyenv/versions/ml-env/bin/python -m src.main
```

## Deployment

```bash
bash scripts/deploy.sh
```

The script copies `src/` to `~/bin/feed_harvester/`, installs dependencies into ml-env, installs the systemd unit, and restarts the service.

## Service management

```bash
systemctl --user start feed-harvester
systemctl --user stop feed-harvester
systemctl --user restart feed-harvester
systemctl --user status feed-harvester
journalctl --user -u feed-harvester -f
```

## Fetch behaviour

| Parameter | Default | Env var |
|---|---|---|
| Fetch interval | 30 min | `FETCH_INTERVAL_MINUTES` |
| Interval jitter | ±5 min | `FETCH_INTERVAL_JITTER_MINUTES` |
| Tweets per fetch | 15–20 | `MIN_TWEETS_PER_FETCH` / `MAX_TWEETS_PER_FETCH` |
| Inter-account delay | 2–7s random | — |
| Quiet hours | 01:00–06:00 | `QUIET_HOUR_START` / `QUIET_HOUR_END` |

## Telegram bot commands

| Command | Description |
|---|---|
| `/digest` | Trigger immediate digest of all unseen tweets |
| `/expand <handle>` | Gemini deep-dive on that account's unseen tweets |
| `/raw <handle>` | Return raw unseen tweet texts for that account |
| `/since <handle> <Nd>` | Tweets from the last N days regardless of seen status |
| `/status` | Count of unseen tweets per account |
| `/help` | List all available commands |

## SQLite schema

```sql
CREATE TABLE tweets (
    tweet_id      TEXT PRIMARY KEY,
    author_handle TEXT NOT NULL,
    text          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    url           TEXT,
    fetched_at    TEXT NOT NULL,
    digested_at   TEXT   -- NULL = unseen
);
```

## Known issues and workarounds

### twikit compatibility patches

Two monkey-patches are applied at startup in `src/fetcher.py`:

1. **`ClientTransaction`** — Twitter removed the `ondemand.s` JS bundle that twikit uses to generate `x-client-transaction-id` headers. The init and transaction ID generation are replaced with no-ops.

2. **`User.__init__`** — Twitter's API omits some user fields (e.g. `withheld_in_countries`) for certain accounts. All field access is patched to use `.get()` with safe defaults.

These patches are in source and survive twikit reinstalls.
