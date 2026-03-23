"""
Session Manager — in-memory conversation context store.
Stores last 5 message pairs per chat_id with 30-min TTL.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_TTL = 30 * 60  # 30 minutes
MAX_HISTORY_PAIRS = 5  # 5 user+assistant pairs = 10 messages


@dataclass
class LeadData:
    """Tracks lead capture state for a conversation."""
    collecting: bool = False
    name: Optional[str] = None
    email: Optional[str] = None
    enquiry_type: Optional[str] = None
    step: str = "name"  # name → email → enquiry_type → done


@dataclass
class Session:
    """Stores per-user conversation state."""
    chat_id: int
    history: list[dict] = field(default_factory=list)
    lead: LeadData = field(default_factory=LeadData)
    last_active: float = field(default_factory=time.time)

    def add_turn(self, user_msg: str, assistant_msg: str):
        self.history.append({"role": "user", "content": user_msg})
        self.history.append({"role": "assistant", "content": assistant_msg})
        # Keep only last N pairs
        if len(self.history) > MAX_HISTORY_PAIRS * 2:
            self.history = self.history[-(MAX_HISTORY_PAIRS * 2):]
        self.last_active = time.time()

    def get_history(self) -> list[dict]:
        return self.history.copy()

    def is_expired(self) -> bool:
        return time.time() - self.last_active > SESSION_TTL

    def reset_lead(self):
        self.lead = LeadData()

    def start_lead_capture(self):
        self.lead = LeadData(collecting=True)


class SessionManager:
    """In-memory session store with TTL cleanup."""

    def __init__(self):
        self._sessions: dict[int, Session] = {}

    def get(self, chat_id: int) -> Session:
        """Get or create a session for chat_id."""
        session = self._sessions.get(chat_id)
        if session is None or session.is_expired():
            session = Session(chat_id=chat_id)
            self._sessions[chat_id] = session
        return session

    def cleanup_expired(self):
        """Remove expired sessions to free memory."""
        expired = [cid for cid, s in self._sessions.items() if s.is_expired()]
        for cid in expired:
            del self._sessions[cid]
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))


# Global singleton
sessions = SessionManager()
