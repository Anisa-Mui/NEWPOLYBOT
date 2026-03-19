# 🤖 Polymarket Signal Filter Bot

A Telegram bot that scans Polymarket, scores markets by tradability,
and sends you the top picks. **You decide which trades to take — it never touches money.**

---

## What it does

| Feature | Detail |
|---|---|
| `/scan` | Fetches up to 300 active markets, scores all of them, returns top picks |
| Auto-scan | Pushes signals every N hours (default: 6) |
| Scoring | Price edge 40% · Liquidity 30% · 24h Volume 20% · Urgency 10% |
| Filters | Drops markets priced >85¢ or <15¢ (near-certain outcomes) |
| Safety | `ALLOWED_USER_IDS` locks the bot to only you |

---

## Files

```
bot.py            ← the entire bot
requirements.txt  ← two dependencies
Procfile          ← tells Railway how to run it
.env.example      ← environment variable template
```

---

## Deployment on Railway (free, 24/7)

### Step 1 — Get a Telegram bot token
1. Open Telegram → search **@BotFather** → `/newbot`
2. Follow the prompts, copy your **bot token** (looks like `123456:ABCdef...`)
3. Open Telegram → search **@userinfobot** → copy your **numeric user ID**

### Step 2 — Push to GitHub
1. Create a free account at [github.com](https://github.com)
2. New repository (can be private) → upload these 4 files:
   - `bot.py`
   - `requirements.txt`
   - `Procfile`
   - `.env.example` (optional, just for reference)

### Step 3 — Deploy on Railway
1. Go to [railway.app](https://railway.app) → sign up with GitHub (free)
2. **New Project** → **Deploy from GitHub repo** → select your repo
3. Go to **Variables** tab → add:
   ```
   TELEGRAM_BOT_TOKEN   = <paste your token>
   ALLOWED_USER_IDS     = <paste your numeric ID>
   AUTO_SCAN_HOURS      = 6
   TOP_RESULTS          = 10
   ```
4. Railway auto-detects `Procfile` and runs `python bot.py`
5. Wait ~60 seconds for the first deploy to finish

### Step 4 — Test it
- Open Telegram → find your bot (by the username you gave BotFather)
- Send `/scan`
- You'll get the top Polymarket signals within a few seconds

---

## Running locally

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Set secrets
export TELEGRAM_BOT_TOKEN=your_token_here
export ALLOWED_USER_IDS=your_id_here

# 3. Run
python bot.py
```

---

## Scoring explained

Each market is scored out of 100:

- **Price edge (40%)** — markets priced near 50¢ are the most uncertain and offer the best edge; extreme prices (>85¢ / <15¢) are filtered out entirely.
- **Liquidity (30%)** — higher on-chain liquidity means you can enter and exit without slippage.
- **24h Volume (20%)** — active trading signals market participants are paying attention.
- **Urgency (10%)** — markets closing within 7 days get a boost; resolution is near.

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | From @BotFather |
| `ALLOWED_USER_IDS` | ✅ | — | Comma-separated numeric Telegram user IDs |
| `AUTO_SCAN_HOURS` | ❌ | `6` | How often to auto-push signals (hours) |
| `TOP_RESULTS` | ❌ | `10` | Number of markets to show per scan |
