"""
Lead Capture — saves qualified leads to Google Sheets via gspread.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = ["Timestamp", "Name", "Email", "Enquiry Type", "Chat ID", "Source"]


def _get_sheet():
    """Authenticate and return the Google Sheet worksheet."""
    creds_json = os.environ.get("GOOGLE_CREDS_JSON", "")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")

    if not creds_json or not sheet_id:
        logger.warning("Google Sheets credentials not configured — leads will not be saved.")
        return None

    try:
        creds_data = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)

        try:
            ws = sh.worksheet("Leads")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="Leads", rows=1000, cols=10)
            ws.append_row(SHEET_HEADERS)

        return ws
    except Exception:
        logger.exception("Failed to connect to Google Sheets")
        return None


def save_lead(
    name: str,
    email: str,
    enquiry_type: str,
    chat_id: int,
    source: str = "Telegram",
) -> bool:
    """
    Save a lead to Google Sheets.
    Returns True on success, False on failure.
    """
    ws = _get_sheet()
    if ws is None:
        logger.info(
            "Lead (not saved to Sheet): name=%s email=%s enquiry=%s",
            name, email, enquiry_type,
        )
        return False

    try:
        row = [
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            name,
            email,
            enquiry_type,
            str(chat_id),
            source,
        ]
        ws.append_row(row)
        logger.info("Lead saved to Google Sheet: %s <%s>", name, email)
        return True
    except Exception:
        logger.exception("Failed to save lead to Google Sheets")
        return False


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


# Lead capture conversation flow messages
LEAD_MESSAGES = {
    "start": (
        "I'd love to connect you with our team! Let me collect a few quick details.\n\n"
        "What's your name?"
    ),
    "ask_email": "Thanks, {name}! What's your email address so our team can follow up?",
    "ask_enquiry": (
        "Got it! What are you enquiring about?\n\n"
        "1. EV Charger installation\n"
        "2. Solar PV system\n"
        "3. Solar + EV Bundle\n"
        "4. Maintenance / Fault report\n"
        "5. Other\n\n"
        "Reply with the number or type your enquiry."
    ),
    "done": (
        "Thank you, {name}! Your details have been recorded. "
        "Our team will reach out to {email} within 1 business day. "
        "Is there anything else I can help you with?"
    ),
}

ENQUIRY_MAP = {
    "1": "EV Charger Installation",
    "2": "Solar PV System",
    "3": "Solar + EV Bundle",
    "4": "Maintenance / Fault Report",
    "5": "Other",
}
