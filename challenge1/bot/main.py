"""
SuperCharge SG — AI Customer Support Bot
Platform: Telegram (python-telegram-bot v20.x) + FastAPI webhook

Intents handled:
1. EV Charger enquiry
2. Solar Panel enquiry
3. Price / Quote request
4. Maintenance / Fault report
5. General FAQ
6. Human agent request
7. Lead capture (cross-cutting)
8. Greeting
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .rag_pipeline import rag
from .intent_router import classify_intent, Intent
from .session_manager import sessions
from .lead_capture import (
    save_lead,
    validate_email,
    LEAD_MESSAGES,
    ENQUIRY_MAP,
)
from .escalation import (
    send_escalation_alert,
    build_conversation_summary,
    CONFIDENCE_THRESHOLD,
    HANDOFF_MESSAGE,
    LOW_CONFIDENCE_HANDOFF_MESSAGE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g. https://yourapp.railway.app

# ── Telegram Application ────────────────────────────────────────────────────
telegram_app = Application.builder().token(BOT_TOKEN).build()
bot = Bot(token=BOT_TOKEN)


# ── Greeting templates ──────────────────────────────────────────────────────
GREETING_RESPONSE = (
    "👋 Hello! I'm the SuperCharge SG virtual assistant.\n\n"
    "I can help you with:\n"
    "• EV charger installation & enquiries\n"
    "• Solar panel systems & pricing\n"
    "• ECIS export credits\n"
    "• TR25 compliance questions\n"
    "• Maintenance & fault reports\n"
    "• Connecting you to our support team\n\n"
    "What can I help you with today?"
)


# ── Core message handler ────────────────────────────────────────────────────
async def handle_message(update: Update, context) -> None:
    """Main message handler — routes by intent and manages conversation flow."""
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    user_name = update.effective_user.first_name if update.effective_user else None

    session = sessions.get(chat_id)

    # ── Lead capture flow (stateful, intercepts normal flow) ────────────────
    if session.lead.collecting:
        await _handle_lead_capture_step(update, session, user_text, user_name)
        return

    # ── Intent detection ────────────────────────────────────────────────────
    intent = classify_intent(user_text)
    logger.info("chat_id=%d intent=%s msg=%r", chat_id, intent, user_text[:80])

    # ── Greeting ────────────────────────────────────────────────────────────
    if intent == Intent.GREETING:
        await update.message.reply_text(GREETING_RESPONSE)
        session.add_turn(user_text, GREETING_RESPONSE)
        return

    # ── Human agent request ─────────────────────────────────────────────────
    if intent == Intent.HUMAN_AGENT:
        summary = build_conversation_summary(session.get_history())
        await send_escalation_alert(chat_id, user_name, "User requested human agent", summary)
        await update.message.reply_text(HANDOFF_MESSAGE)
        session.add_turn(user_text, HANDOFF_MESSAGE)
        return

    # ── Lead capture trigger ────────────────────────────────────────────────
    if intent == Intent.LEAD_CAPTURE:
        session.start_lead_capture()
        msg = LEAD_MESSAGES["start"]
        await update.message.reply_text(msg)
        session.add_turn(user_text, msg)
        return

    # ── RAG-powered response (all other intents) ────────────────────────────
    history = session.get_history()
    response, confidence = rag.query(user_text, history)

    # Auto-escalate on low confidence
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(
            "Low confidence (%.2f) for chat_id=%d — escalating", confidence, chat_id
        )
        summary = build_conversation_summary(history)
        await send_escalation_alert(
            chat_id,
            user_name,
            f"Low RAG confidence ({confidence:.0%}) on: {user_text[:100]}",
            summary,
        )
        # Append handoff note to response
        response = response + "\n\n" + LOW_CONFIDENCE_HANDOFF_MESSAGE

    await update.message.reply_text(response)
    session.add_turn(user_text, response)

    # Check if response contains lead capture invitation
    lead_phrases = ["contact us", "site assessment", "schedule", "book a visit"]
    if any(phrase in response.lower() for phrase in lead_phrases) and not session.lead.collecting:
        follow_up = "\n\nWould you like me to connect you with our team for a free consultation? Just say 'yes' or 'I'm interested'."
        await update.message.reply_text(follow_up)


async def _handle_lead_capture_step(update, session, user_text: str, user_name: str | None):
    """Handle multi-turn lead capture conversation."""
    lead = session.lead
    chat_id = update.effective_chat.id

    if lead.step == "name":
        lead.name = user_text.strip()
        lead.step = "email"
        msg = LEAD_MESSAGES["ask_email"].format(name=lead.name)
        await update.message.reply_text(msg)
        session.add_turn(user_text, msg)

    elif lead.step == "email":
        email = user_text.strip()
        if not validate_email(email):
            msg = "That doesn't look like a valid email address. Please try again (e.g. john@example.com):"
            await update.message.reply_text(msg)
            return
        lead.email = email
        lead.step = "enquiry_type"
        msg = LEAD_MESSAGES["ask_enquiry"]
        await update.message.reply_text(msg)
        session.add_turn(user_text, msg)

    elif lead.step == "enquiry_type":
        # Accept number (1-5) or free text
        enquiry = ENQUIRY_MAP.get(user_text.strip(), user_text.strip())
        lead.enquiry_type = enquiry
        lead.step = "done"
        lead.collecting = False

        # Save to Google Sheets
        saved = save_lead(
            name=lead.name,
            email=lead.email,
            enquiry_type=lead.enquiry_type,
            chat_id=chat_id,
            source="Telegram",
        )

        msg = LEAD_MESSAGES["done"].format(name=lead.name, email=lead.email)
        await update.message.reply_text(msg)
        session.add_turn(user_text, msg)
        session.reset_lead()


# ── /start command ──────────────────────────────────────────────────────────
async def start_command(update: Update, context) -> None:
    """Handle /start."""
    await update.message.reply_text(GREETING_RESPONSE)


# ── /help command ───────────────────────────────────────────────────────────
async def help_command(update: Update, context) -> None:
    """Handle /help."""
    help_text = (
        "SuperCharge SG Customer Support Bot\n\n"
        "Commands:\n"
        "/start — Welcome message\n"
        "/help — Show this help\n"
        "/contact — Get contact details\n\n"
        "Just type your question and I'll do my best to help! "
        "Type 'speak to a person' anytime to reach our team."
    )
    await update.message.reply_text(help_text)


async def contact_command(update: Update, context) -> None:
    """Handle /contact."""
    msg = (
        "📞 Contact SuperCharge SG:\n\n"
        "🌐 Website: supercharge.sg\n"
        "📧 Email: support@supercharge.sg\n\n"
        "Our team is available Mon–Fri, 9 AM–6 PM SGT.\n"
        "We typically respond within 1 business day."
    )
    await update.message.reply_text(msg)


# ── FastAPI app + webhook ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise RAG pipeline and set Telegram webhook."""
    logger.info("Initialising RAG pipeline…")
    rag.initialize()

    logger.info("Setting Telegram webhook to %s", WEBHOOK_URL)
    await telegram_app.initialize()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

    # Register handlers
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("contact", contact_command))
    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    yield

    # Teardown
    await telegram_app.shutdown()
    logger.info("Bot shutdown cleanly.")


app = FastAPI(title="SuperCharge SG Telegram Bot", lifespan=lifespan)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates."""
    body = await request.json()
    update = Update.de_json(body, bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "bot": "SuperCharge SG Support Bot"}


@app.get("/")
async def root():
    return {"message": "SuperCharge SG AI Support Bot is running."}


if __name__ == "__main__":
    uvicorn.run("bot.main:app", host="0.0.0.0", port=8000, reload=False)
