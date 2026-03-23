"""
Intent Router — classifies user messages into one of 6 required intents.
Uses keyword heuristics first; falls back to LLM classification for ambiguous inputs.
"""

import re
import os
import logging
from enum import Enum
from openai import OpenAI

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    EV_CHARGER = "ev_charger"
    SOLAR_PANEL = "solar_panel"
    PRICE_QUOTE = "price_quote"
    MAINTENANCE_FAULT = "maintenance_fault"
    GENERAL_FAQ = "general_faq"
    HUMAN_AGENT = "human_agent"
    LEAD_CAPTURE = "lead_capture"
    GREETING = "greeting"


# ── Keyword maps ───────────────────────────────────────────────────────────
_KEYWORD_MAP: list[tuple[list[str], Intent]] = [
    (
        ["speak to", "talk to", "human", "agent", "person", "staff", "representative", "support team"],
        Intent.HUMAN_AGENT,
    ),
    (
        ["ev charger", "ev charging", "electric vehicle", "charger", "charging point",
         "type 2", "ccs2", "ocpp", "7kw", "22kw", "50kw", "dc fast", "home charger",
         "charge my car", "install charger", "overnight charge", "charge ev"],
        Intent.EV_CHARGER,
    ),
    (
        ["solar panel", "solar pv", "solar system", "solar installation", "solar energy",
         "rooftop solar", "photovoltaic", "pv system", "solar farm", "sun", "solar quote",
         "install solar", "kwp", "inverter", "ecis", "export credit", "sp group", "solarno"],
        Intent.SOLAR_PANEL,
    ),
    (
        ["price", "cost", "how much", "quote", "pricing", "rate", "fee", "charge",
         "estimate", "afford", "expensive", "cheap", "value", "sgd", "$"],
        Intent.PRICE_QUOTE,
    ),
    (
        ["fault", "broken", "not working", "error", "issue", "problem", "malfunction",
         "maintenance", "repair", "fix", "down", "offline", "failure", "alarm", "alert",
         "ocpp error", "charger down", "not charging"],
        Intent.MAINTENANCE_FAULT,
    ),
    (
        ["interested", "want to", "would like", "get started", "sign up", "contact",
         "schedule", "appointment", "assess", "site visit", "learn more", "tell me more"],
        Intent.LEAD_CAPTURE,
    ),
    (
        ["hi", "hello", "hey", "good morning", "good afternoon", "good evening",
         "howdy", "greetings", "hiya", "what can you do", "help me"],
        Intent.GREETING,
    ),
]


def classify_intent(message: str) -> Intent:
    """
    Classify user message into an Intent.
    Uses keyword matching first; falls back to LLM for ambiguous inputs.
    """
    lower = message.lower()
    lower = re.sub(r"[^\w\s]", " ", lower)

    for keywords, intent in _KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            return intent

    # LLM fallback for ambiguous messages
    return _llm_classify(message)


def _llm_classify(message: str) -> Intent:
    """Use LLM to classify ambiguous messages."""
    try:
        oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        prompt = f"""Classify this customer message into exactly one of these intents:
- ev_charger: questions about EV chargers, charging, OCPP
- solar_panel: questions about solar panels, solar PV, ECIS export credits
- price_quote: asking for pricing, cost, quotes
- maintenance_fault: reporting a fault, error, or maintenance request
- general_faq: general questions about the company, compliance, TR25, warranties
- human_agent: wants to speak to a human, escalation request
- lead_capture: expressing interest, wanting a site visit or consultation
- greeting: greetings or introductions

Message: "{message}"

Reply with ONLY the intent name, nothing else."""

        resp = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
        )
        intent_str = resp.choices[0].message.content.strip().lower()
        return Intent(intent_str)
    except Exception:
        logger.exception("LLM intent classification failed, defaulting to general_faq")
        return Intent.GENERAL_FAQ
