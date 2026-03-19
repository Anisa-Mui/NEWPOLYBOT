import os
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Debug ─────────────────────────────────────────────────────────────────────
log.info("=== ENV CHECK ===")
log.info("TELEGRAM_BOT_TOKEN present: %s", "TELEGRAM_BOT_TOKEN" in os.environ)
log.info("ALLOWED_USER_IDS present:   %s", "ALLOWED_USER_IDS"   in os.environ)
log.info("=================")

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    log.critical("TELEGRAM_BOT_TOKEN is missing! Add it in Railway Variables then redeploy.")
    raise SystemExit(1)

ALLOWED_IDS = set(
    int(x.strip())
    for x in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if x.strip()
)
AUTO_SCAN_HOURS = int(os.environ.get("AUTO_SCAN_HOURS", "6"))
TOP_N           = int(os.environ.get("TOP_RESULTS", "10"))

log.info("Config loaded. ALLOWED_IDS=%s AUTO_SCAN=%dh", ALLOWED_IDS, AUTO_SCAN_HOURS)

# ── Polymarket API ─────────────────────────────────────────────────────────────
GAMMA_API = "https://gamma-api.polymarket.com"
HEADERS   = {"User-Agent": "PolySignalBot/1.0"}


async def fetch_markets(limit: int = 300) -> list[dict]:
    params = {
        "active": "true", "closed": "false",
        "limit": limit, "order": "volume24hr", "ascending": "false",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{GAMMA_API}/markets", params=params, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("markets", data.get("data", []))


def parse_price(market: dict) -> Optional[float]:
    try:
        outcomes = market.get("outcomePrices") or []
        if isinstance(outcomes, str):
            import json
            outcomes = json.loads(outcomes)
        if isinstance(outcomes, list) and outcomes:
            return float(outcomes[0])
        tokens = market.get("tokens") or []
        if tokens:
            return float(tokens[0].get("price", 0))
    except (TypeError, ValueError):
        pass
    return None


def days_to_close(market: dict) -> Optional[float]:
    end_str = market.get("endDate") or market.get("endDateIso")
    if not end_str:
        return None
    try:
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        return (end - datetime.now(timezone.utc)).total_seconds() / 86400
    except ValueError:
        return None


def score_market(market: dict) -> float:
    price = parse_price(market)
    if price is None or price > 0.85 or price < 0.15:
        return 0.0
    liq   = float(market.get("liquidity")  or 0)
    vol24 = float(market.get("volume24hr") or 0)
    days  = days_to_close(market)
    price_score = 1 - abs(price - 0.5) * 2
    liq_score   = min(liq,   500_000) / 500_000
    vol_score   = min(vol24, 100_000) / 100_000
    if days is None or days > 30 or days <= 0:
        time_score = 0.0
    elif days <= 7:
        time_score = 1.0
    else:
        time_score = (30 - days) / 23
    return price_score*40 + liq_score*30 + vol_score*20 + time_score*10


def format_market(rank: int, market: dict, score: float) -> str:
    price    = parse_price(market) or 0
    liq      = float(market.get("liquidity")  or 0)
    vol24    = float(market.get("volume24hr") or 0)
    days     = days_to_close(market)
    slug     = market.get("slug") or market.get("conditionId", "")
    url      = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"
    question = (market.get("question") or market.get("title") or "Unknown")[:120]
    days_str = f"{days:.1f}d" if days is not None else "N/A"
    return (
        f"{'─'*36}\n"
        f"#{rank}  Score: {score:.1f}/100\n"
        f"{question}\n"
        f"YES: {price:.0%}  |  Liq: ${liq:,.0f}  |  Vol24h: ${vol24:,.0f}\n"
        f"Closes: {days_str}  |  {url}\n"
    )


async def run_scan() -> str:
    markets = await fetch_markets(300)
    if not markets:
        return "Polymarket API returned nothing. Try again shortly."
    scored = sorted(
        [(m, score_market(m)) for m in markets if score_market(m) > 0],
        key=lambda x: x[1], reverse=True
    )[:TOP_N]
    if not scored:
        return "No qualifying markets right now. Try again later."
    header = (
        f"*Polymarket Signal Filter*\n"
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Scanned {len(markets)} markets, top {len(scored)} picks:\n\n"
    )
    lines  = [format_market(i+1, m, s) for i, (m, s) in enumerate(scored)]
    footer = "\nSignals only — you decide the trade.\nScore = Price edge 40% | Liquidity 30% | Volume 20% | Urgency 10%"
    return header + "\n".join(lines) + footer


# ── Auth ───────────────────────────────────────────────────────────────────────
def auth(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if ALLOWED_IDS and uid not in ALLOWED_IDS:
            await update.message.reply_text("Unauthorized.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Handlers ───────────────────────────────────────────────────────────────────
@auth
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"*Bot is live!*\n\n"
        f"Fetching real Polymarket signals.\n\n"
        f"Commands:\n/scan — run a scan now\n/help — this message\n\n"
        f"Auto-scan every {AUTO_SCAN_HOURS} hours.",
        parse_mode="Markdown",
    )

@auth
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)

@auth
async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Scanning Polymarket, please wait...")
    try:
        result = await run_scan()
        await msg.edit_text(result, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        log.exception("Scan failed")
        await msg.edit_text(f"Error: {e}")


async def auto_scan(ctx: ContextTypes.DEFAULT_TYPE):
    log.info("Auto-scan running...")
    try:
        result = await run_scan()
    except Exception as e:
        log.exception("Auto-scan error: %s", e)
        return
    for uid in ALLOWED_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=uid, text=result,
                parse_mode="Markdown", disable_web_page_preview=True
            )
        except TelegramError as e:
            log.warning("Could not message %s: %s", uid, e)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("scan",  cmd_scan))
    if app.job_queue and ALLOWED_IDS:
        app.job_queue.run_repeating(
            auto_scan,
            interval=AUTO_SCAN_HOURS * 3600,
            first=60,
        )
        log.info("Auto-scan every %d hours.", AUTO_SCAN_HOURS)
    log.info("Bot started successfully.")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
