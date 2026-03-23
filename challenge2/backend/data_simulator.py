"""
Data Simulator — generates realistic solar inverter and EV charging telemetry.
Pushes to the database every 30 seconds via APScheduler.
"""

import logging
import math
import random
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Site, SolarReading, EVSession, AnomalyLog
from .nasa_api import get_current_irradiance_kwh_m2_day, expected_yield_kw
from .anomaly_detector import detector

logger = logging.getLogger(__name__)

# Fault injections: {site_id: output_reduction_pct}
FAULT_INJECTIONS: dict[str, float] = {}

# EV charger statuses (OCPP-style)
EV_STATUSES = ["Available", "Preparing", "Charging", "SuspendedEV", "Finishing", "Faulted"]

ECIS_RATE = 0.218  # SGD/kWh — Enhanced Central Intermediary Scheme baseline
EV_CHARGE_RATE = 0.50  # SGD/kWh charged to EV users (average)
CO2_FACTOR = 0.4085  # kg CO2/kWh (Singapore grid, EMA 2024)


def simulate_solar_reading(site: Site, irradiance: float, ts: datetime) -> SolarReading:
    """
    Generate a realistic solar reading for a site.
    Simulates diurnal variation, cloud noise, and optional fault injection.
    """
    hour = ts.hour + ts.minute / 60.0

    # Diurnal solar curve — peaks at noon, zero at night
    solar_fraction = max(0.0, math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else 0.0)

    # Add cloud noise (±10%)
    cloud_noise = random.gauss(1.0, 0.08)
    cloud_noise = max(0.3, min(1.2, cloud_noise))

    # Panel temperature (ambient + solar heating)
    temp_c = 28 + solar_fraction * 20 + random.gauss(0, 2)

    # Expected output based on irradiance
    irr_instantaneous = irradiance * solar_fraction  # kWh/m2 at this instant
    exp_kw = expected_yield_kw(site.solar_kwp, irr_instantaneous * (1000 / 4.5))
    exp_kw = max(0.0, exp_kw)

    # Apply fault injection if active
    fault_reduction = FAULT_INJECTIONS.get(str(site.id), 1.0)
    if isinstance(fault_reduction, float) and fault_reduction != 1.0:
        # fault_reduction is a percentage (e.g. 60 means 60% reduction → 40% output)
        actual_multiplier = (100 - fault_reduction) / 100
    else:
        actual_multiplier = 1.0

    actual_kw = max(0.0, exp_kw * cloud_noise * actual_multiplier)

    # Performance ratio
    pr = (actual_kw / exp_kw) if exp_kw > 0 else 1.0
    pr = min(pr, 1.2)

    # % deviation from expected
    if exp_kw > 0:
        deviation_pct = ((actual_kw - exp_kw) / exp_kw) * 100
    else:
        deviation_pct = 0.0

    # Cumulative energy (rough daily accumulation, reset at midnight)
    minutes_since_dawn = max(0, hour - 6) * 60
    energy_kwh = actual_kw * (minutes_since_dawn / 60) * 0.8  # rough integral

    # Score anomaly
    result = detector.score_reading(
        performance_ratio=pr,
        actual_vs_expected_pct=deviation_pct,
        temp_c=temp_c,
        irradiance=irr_instantaneous,
    )

    return SolarReading(
        site_id=site.id,
        ts=ts,
        power_kw=round(actual_kw, 3),
        energy_kwh=round(energy_kwh, 2),
        irradiance=round(irr_instantaneous, 3),
        temp_c=round(temp_c, 1),
        expected_kw=round(exp_kw, 3),
        performance_ratio=round(pr, 3),
        actual_vs_expected_pct=round(deviation_pct, 2),
        anomaly_flag=result.is_anomaly,
        anomaly_severity=result.severity,
    )


def simulate_ev_sessions(site: Site, db: Session, ts: datetime) -> None:
    """
    Update active EV charging sessions for a site.
    Creates new sessions and updates ongoing ones.
    """
    # Close any sessions that ran for >2 hours
    active_sessions = (
        db.query(EVSession)
        .filter(EVSession.site_id == site.id, EVSession.end_ts.is_(None))
        .all()
    )

    for session in active_sessions:
        elapsed_hours = (ts - session.start_ts.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if elapsed_hours > random.uniform(1.0, 3.0):
            session.end_ts = ts
            session.energy_kwh = round(elapsed_hours * 7.2, 2)  # 7.2kW charger
            session.revenue_sgd = round(session.energy_kwh * EV_CHARGE_RATE, 2)
            session.status = "Finishing"

    # Randomly start new charging sessions
    if site.charger_count > 0 and random.random() < 0.15:
        charger_id = f"CHR-{site.id[:4]}-{random.randint(1, site.charger_count):02d}"
        new_session = EVSession(
            site_id=site.id,
            charger_id=charger_id,
            start_ts=ts,
            energy_kwh=0.0,
            revenue_sgd=0.0,
            status="Charging",
        )
        db.add(new_session)


def run_simulation_tick() -> None:
    """
    Called every 30 seconds by the scheduler.
    Generates solar readings and EV session updates for all sites.
    """
    db: Session = SessionLocal()
    try:
        sites = db.query(Site).all()
        if not sites:
            return

        ts = datetime.now(timezone.utc)
        irradiance = get_current_irradiance_kwh_m2_day()

        for site in sites:
            if site.solar_kwp > 0:
                reading = simulate_solar_reading(site, irradiance, ts)
                db.add(reading)

                # Log anomaly events separately
                if reading.anomaly_flag:
                    existing = (
                        db.query(AnomalyLog)
                        .filter(
                            AnomalyLog.site_id == site.id,
                            AnomalyLog.resolved.is_(False),
                        )
                        .first()
                    )
                    if not existing:
                        db.add(AnomalyLog(
                            site_id=site.id,
                            ts=ts,
                            severity=reading.anomaly_severity,
                            actual_kw=reading.power_kw,
                            expected_kw=reading.expected_kw,
                            deviation_pct=reading.actual_vs_expected_pct,
                            description=(
                                f"Output {abs(reading.actual_vs_expected_pct):.1f}% "
                                f"below expected. Severity: {reading.anomaly_severity}"
                            ),
                        ))

            if site.charger_count > 0:
                simulate_ev_sessions(site, db, ts)

        db.commit()
        logger.debug("Simulation tick: %d sites updated at %s", len(sites), ts.isoformat())

    except Exception:
        logger.exception("Simulation tick failed")
        db.rollback()
    finally:
        db.close()
