"""
Escalation — sends human handoff alerts via Slack webhook and/or email.
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.40  # Below this, escalate automatically


async def send_escalation_alert(
    chat_id: int,
    user_name: Optional[str],
    reason: str,
    conversation_summary: str,
) -> bool:
    """
    Send a human handoff alert via Slack webhook and/or email.
    Returns True if at least one channel succeeded.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    success = False

    slack_ok = await _send_slack(chat_id, user_name, reason, conversation_summary, timestamp)
    email_ok = _send_email(chat_id, user_name, reason, conversation_summary, timestamp)

    return slack_ok or email_ok


async def _send_slack(
    chat_id: int,
    user_name: Optional[str],
    reason: str,
    summary: str,
    timestamp: str,
) -> bool:
    """Post escalation alert to Slack webhook."""
    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not slack_url:
        logger.info("Slack webhook not configured — skipping Slack alert.")
        return False

    payload = {
        "text": f":sos: *SuperCharge Bot — Human Handoff Required*",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🆘 Customer Needs Human Support"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Chat ID:*\n{chat_id}"},
                    {"type": "mrkdwn", "text": f"*Name:*\n{user_name or 'Unknown'}"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n{reason}"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{timestamp}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Conversation Summary:*\n{summary[:500]}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Platform: Telegram | Bot: SuperCharge SG Support"}
                ],
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(slack_url, json=payload)
        if resp.status_code == 200:
            logger.info("Slack escalation alert sent for chat_id=%d", chat_id)
            return True
        logger.warning("Slack returned %d for escalation", resp.status_code)
        return False
    except Exception:
        logger.exception("Failed to send Slack escalation alert")
        return False


def _send_email(
    chat_id: int,
    user_name: Optional[str],
    reason: str,
    summary: str,
    timestamp: str,
) -> bool:
    """Send escalation alert via email (SMTP)."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_email = os.environ.get("ESCALATION_EMAIL", "support@supercharge.sg")

    if not smtp_host or not smtp_user:
        logger.info("SMTP not configured — skipping email alert.")
        return False

    subject = f"[SuperCharge Bot] Human Handoff Required — Chat {chat_id}"
    body = f"""
SuperCharge SG Customer Support Bot — Human Handoff Alert
==========================================================

Chat ID    : {chat_id}
User Name  : {user_name or 'Unknown'}
Reason     : {reason}
Timestamp  : {timestamp}

Conversation Summary:
{summary}

---
Please follow up with this customer as soon as possible.
SuperCharge SG Support Bot
"""

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Email escalation alert sent to %s for chat_id=%d", to_email, chat_id)
        return True
    except Exception:
        logger.exception("Failed to send email escalation alert")
        return False


def build_conversation_summary(history: list[dict]) -> str:
    """Build a readable summary of recent conversation turns."""
    if not history:
        return "No prior conversation history."
    lines = []
    for msg in history[-10:]:
        role = "User" if msg["role"] == "user" else "Bot"
        lines.append(f"{role}: {msg['content'][:200]}")
    return "\n".join(lines)


HANDOFF_MESSAGE = (
    "I've alerted our support team and a human agent will follow up with you "
    "shortly (usually within 1 business day). In the meantime, you can also "
    "reach us at support@supercharge.sg. Is there anything else I can try to help with?"
)

LOW_CONFIDENCE_HANDOFF_MESSAGE = (
    "I want to make sure you get an accurate answer on this. I've flagged your "
    "question for our team, and a human agent will follow up with you shortly. "
    "You can also email us at support@supercharge.sg."
)
