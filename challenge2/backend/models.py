"""
SQLAlchemy models — multi-tenant time-series schema for Smart Energy Dashboard.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Integer, String, Text,
    TIMESTAMP, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid():
    return str(uuid.uuid4())


class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="org", cascade="all, delete-orphan")
    sites = relationship("Site", back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    org = relationship("Organisation", back_populates="users")


class Site(Base):
    __tablename__ = "sites"

    id = Column(String(36), primary_key=True, default=_uuid)
    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False, default=1.3521)
    lng = Column(Float, nullable=False, default=103.8198)
    solar_kwp = Column(Float, default=0.0)      # Installed solar capacity
    charger_count = Column(Integer, default=0)  # Number of EV chargers

    org = relationship("Organisation", back_populates="sites")
    solar_readings = relationship("SolarReading", back_populates="site", cascade="all, delete-orphan")
    ev_sessions = relationship("EVSession", back_populates="site", cascade="all, delete-orphan")


class SolarReading(Base):
    """
    One row per simulated solar inverter reading (~every 30 seconds).
    """
    __tablename__ = "solar_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(36), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    power_kw = Column(Float, nullable=False)          # Actual output power
    energy_kwh = Column(Float, nullable=False)        # Cumulative energy today
    irradiance = Column(Float, nullable=False)        # W/m² from NASA POWER baseline
    temp_c = Column(Float, nullable=False)            # Panel temperature
    expected_kw = Column(Float, nullable=False)       # Expected output (from irradiance model)
    performance_ratio = Column(Float, nullable=False) # actual/expected
    actual_vs_expected_pct = Column(Float, nullable=False)  # % deviation
    anomaly_flag = Column(Boolean, default=False)
    anomaly_severity = Column(String(20), nullable=True)    # OK / WARNING / CRITICAL

    site = relationship("Site", back_populates="solar_readings")


class EVSession(Base):
    """
    One row per EV charging session.
    """
    __tablename__ = "ev_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(36), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    charger_id = Column(String(50), nullable=False)
    start_ts = Column(TIMESTAMP(timezone=True), nullable=False)
    end_ts = Column(TIMESTAMP(timezone=True), nullable=True)
    energy_kwh = Column(Float, default=0.0)
    revenue_sgd = Column(Float, default=0.0)
    status = Column(String(30), default="Available")  # Available/Preparing/Charging/Faulted

    site = relationship("Site", back_populates="ev_sessions")


class AnomalyLog(Base):
    """Persisted anomaly events for audit log and PDF reports."""
    __tablename__ = "anomaly_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(36), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False)
    severity = Column(String(20), nullable=False)
    actual_kw = Column(Float)
    expected_kw = Column(Float)
    deviation_pct = Column(Float)
    description = Column(Text)
    resolved = Column(Boolean, default=False)
