import re
import time
import json
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot import config
from bot.backlink_provider import (
    fetch_backlinks,
    BacklinkProviderError,
    BacklinkProviderNotConfigured,
)

logger = logging.getLogger(__name__)

_DOMAIN_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?:/.*)?$", re.IGNORECASE
)

_last_lookup: dict[int, float] = {}


def _extract_domain(text: str) -> str | None:
    match = _DOMAIN_RE.match(text.strip())
    if not match:
        return None
    return match.group(1).lower()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *SEO Audit Bot*.\n\n"
        "Send /backlinks <domain> to check a site's backlink profile.\n"
        "Example: `/backlinks example.com`\n\n"
        "Use /help for more.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Commands*\n"
        "/backlinks <domain> — get a backlink summary for a domain\n"
        "/help — show this message\n\n"
        f"To be considerate of the free API quota, lookups are limited to "
        f"one per {config.COOLDOWN_SECONDS}s per user, and results are cached "
        f"for {config.CACHE_TTL_SECONDS // 60} minutes.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def backlinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "Usage: `/backlinks example.com`", parse_mode=ParseMode.MARKDOWN
        )
        return

    domain = _extract_domain(context.args[0])
    if not domain:
        await update.message.reply_text(
            "That doesn't look like a valid domain. Try e.g. `/backlinks example.com`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    now = time.time()
    last = _last_lookup.get(user_id, 0)
    remaining = config.COOLDOWN_SECONDS - (now - last)
    if remaining > 0:
        await update.message.reply_text(
            f"⏳ Please wait {int(remaining)}s before your next lookup."
        )
        return
    _last_lookup[user_id] = now

    await update.message.reply_chat_action("typing")

    try:
        summary = fetch_backlinks(domain)
    except BacklinkProviderNotConfigured as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return
    except BacklinkProviderError as exc:
        await update.message.reply_text(f"❌ {exc}")
        return
    except Exception:
        logger.exception("Unexpected error fetching backlinks for %s", domain)
        await update.message.reply_text(
            "❌ Something unexpected went wrong. Please try again shortly."
        )
        return

    lines = [f"🔗 *Backlink summary for* `{summary.domain}`", ""]
    if summary.total_backlinks is not None:
        lines.append(f"*Total backlinks:* {summary.total_backlinks:,}")
    if summary.referring_domains is not None:
        lines.append(f"*Referring domains:* {summary.referring_domains:,}")

    if summary.sample_links:
        lines.append("")
        lines.append("*Sample backlinks:*")
        for link in summary.sample_links[:10]:
            flag = ""
            if link["dofollow"] is False:
                flag = " (nofollow)"
            anchor = f" — “{link['anchor']}”" if link["anchor"] else ""
            lines.append(f"• {link['source']}{anchor}{flag}")
    elif summary.raw is not None:
        raw_preview = json.dumps(summary.raw, indent=2)[:1500]
        lines.append("")
        lines.append("_Couldn't fully parse the API response. Raw preview:_")
        lines.append(f"```\n{raw_preview}\n```")

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that. Try /help.")
