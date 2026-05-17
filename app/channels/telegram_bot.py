"""Telegram channel integration using python-telegram-bot.

Picks the first agent whose `channels` list contains "telegram" as the entry-point
agent. Every incoming message is routed to it; replies are sent back to the chat.
All conversation is persisted as a Run + Messages so it shows up in the UI.
"""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
)

from app import models
from app.config import TELEGRAM_BOT_TOKEN, has_telegram_token
from app.database import SessionLocal
from app.agents.workflow import execute_single_agent
from app.events import emit

log = logging.getLogger("telegram_bot")


def _pick_telegram_agent(db) -> models.Agent | None:
    """Find the agent designated as the Telegram entry point."""
    agents = db.query(models.Agent).order_by(models.Agent.id.asc()).all()
    for a in agents:
        if a.channels and "telegram" in a.channels:
            return a
    return None


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm a Yuno AI agent. Send me a message and I'll respond. "
        "Use /help for more info."
    )


async def _help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send any text and I'll route it to the agent configured for Telegram in "
        "the platform. Configure agents at the web UI."
    )


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle an incoming text message: route to agent, persist, reply."""
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text or ""

    db = SessionLocal()
    try:
        agent = _pick_telegram_agent(db)
        if not agent:
            await update.message.reply_text(
                "No agent is configured for the Telegram channel yet. "
                "Add one in the web UI (set 'telegram' in channels)."
            )
            return

        emit(
            "telegram_in", chat_id=chat_id, agent_id=agent.id,
            agent_name=agent.name, text=user_text[:500],
        )

        # Remember binding
        binding = db.query(models.TelegramChat).filter_by(chat_id=chat_id).first()
        if not binding:
            binding = models.TelegramChat(chat_id=chat_id, agent_id=agent.id)
            db.add(binding)
        else:
            binding.agent_id = agent.id

        await update.message.chat.send_action("typing")
        run = await execute_single_agent(db, agent, user_text, trigger="telegram")
        binding.last_run_id = run.id
        db.commit()

        reply = run.output or "(no reply)"
        # Telegram max message length is 4096
        for chunk in [reply[i:i + 4000] for i in range(0, len(reply), 4000)] or [reply]:
            await update.message.reply_text(chunk)

        emit("telegram_out", chat_id=chat_id, run_id=run.id, text=reply[:500])
    except Exception as e:
        log.exception("Error handling Telegram message")
        await update.message.reply_text(f"Sorry — an error occurred: {e}")
    finally:
        db.close()


def build_application() -> Application | None:
    """Construct the python-telegram-bot Application, or return None if no token."""
    if not has_telegram_token():
        log.warning("TELEGRAM_BOT_TOKEN not set; Telegram channel disabled.")
        return None
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help", _help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    return app


async def run_polling_in_background(app: Application) -> None:
    """Start the bot polling loop. Designed to be launched as an asyncio task."""
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("Telegram bot polling started")
    # Keep the task alive until cancelled
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception:
            pass
