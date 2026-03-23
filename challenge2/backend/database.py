"""
Database setup — SQLAlchemy with SQLite (dev) or PostgreSQL (production).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./supercharge_dashboard.db",
)

# SQLite needs check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
