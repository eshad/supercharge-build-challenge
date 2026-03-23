"""
SuperCharge SG — Smart Energy Dashboard API
FastAPI backend with JWT multi-tenant auth, WebSocket real-time updates,
anomaly detection, PDF reports, and AI weekly digests.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import (
    Depends, FastAPI, HTTPException, Query,
    WebSocket, WebSocketDisconnect, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .auth import (
    authenticate_user, create_access_token, get_current_org_id, get_current_user,
)
from .database import get_db, init_db
from .models import (
    AnomalyLog, EVSession, Organisation, Site, SolarReading, User,
)
from .anomaly_detector import detector, inject_fault, clear_fault
from .data_simulator import run_simulation_tick, ECIS_RATE, CO2_FACTOR
from .pdf_report import generate_monthly_report
from .weekly_digest import run_weekly_digests, generate_weekly_digest, collect_weekly_site_data
from .seed_data import seed

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


# ── Scheduler ────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising database…")
    init_db()
    seed()

    # Train anomaly model on existing data
    _train_anomaly_model()

    # Simulate data every 30 seconds
    scheduler.add_job(run_simulation_tick, "interval", seconds=30, id="sim_tick")
    # Weekly digest — every Monday at 00:00 UTC (08:00 SGT)
    scheduler.add_job(run_weekly_digests, "cron", day_of_week="mon", hour=0, minute=0, id="weekly_digest")
    scheduler.start()
    logger.info("Scheduler started.")

    yield

    scheduler.shutdown()
    logger.info("API shutdown cleanly.")


def _train_anomaly_model():
    """Train the anomaly detector on any existing solar readings."""
    try:
        from .database import SessionLocal
        import pandas as pd
        db = SessionLocal()
        readings = db.query(SolarReading).limit(5000).all()
        db.close()
        if len(readings) >= 10:
            df = pd.DataFrame([{
                "performance_ratio": r.performance_ratio,
                "actual_vs_expected_pct": r.actual_vs_expected_pct,
                "temp_c": r.temp_c,
                "irradiance": r.irradiance,
            } for r in readings])
            detector.train(df)
    except Exception:
        logger.warning("Could not train anomaly model on startup (no data yet).")


# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="SuperCharge SG — Smart Energy Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Schemas ─────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org_name: str
    org_id: str


class SiteOut(BaseModel):
    id: str
    name: str
    solar_kwp: float
    charger_count: int
    lat: float
    lng: float


class SolarReadingOut(BaseModel):
    ts: str
    power_kw: float
    energy_kwh: float
    irradiance: float
    temp_c: float
    expected_kw: float
    performance_ratio: float
    actual_vs_expected_pct: float
    anomaly_flag: bool
    anomaly_severity: Optional[str]


class AnomalyOut(BaseModel):
    id: int
    site_id: str
    ts: str
    severity: str
    actual_kw: Optional[float]
    expected_kw: Optional[float]
    deviation_pct: Optional[float]
    description: Optional[str]
    resolved: bool


class DashboardSummary(BaseModel):
    total_solar_kw: float
    total_solar_kwh_today: float
    total_ev_sessions_active: int
    total_ev_kwh_today: float
    ecis_credits_month: float
    co2_saved_kg: float
    active_anomalies: int


# ── Auth endpoints ───────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    org = db.query(Organisation).filter(Organisation.id == user.org_id).first()
    token = create_access_token(user_id=user.id, org_id=user.org_id)
    return LoginResponse(
        access_token=token,
        org_name=org.name if org else "",
        org_id=user.org_id,
    )


# ── Sites ────────────────────────────────────────────────────────────────────
@app.get("/sites", response_model=list[SiteOut])
def list_sites(
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Return all sites for the authenticated organisation."""
    sites = db.query(Site).filter(Site.org_id == org_id).all()
    return [SiteOut(
        id=s.id, name=s.name, solar_kwp=s.solar_kwp,
        charger_count=s.charger_count, lat=s.lat, lng=s.lng,
    ) for s in sites]


# ── Solar time-series ────────────────────────────────────────────────────────
@app.get("/solar/readings", response_model=list[SolarReadingOut])
def get_solar_readings(
    site_id: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Get solar readings for a site (last N hours). Enforces org isolation."""
    site = _get_site_or_403(db, site_id, org_id)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    readings = (
        db.query(SolarReading)
        .filter(SolarReading.site_id == site.id, SolarReading.ts >= since)
        .order_by(SolarReading.ts.asc())
        .limit(2000)
        .all()
    )
    return [_reading_out(r) for r in readings]


@app.get("/solar/latest")
def get_solar_latest(
    site_id: str = Query(...),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Get the most recent solar reading for a site."""
    site = _get_site_or_403(db, site_id, org_id)
    r = (
        db.query(SolarReading)
        .filter(SolarReading.site_id == site.id)
        .order_by(SolarReading.ts.desc())
        .first()
    )
    if not r:
        return {"message": "No data yet"}
    return _reading_out(r)


# ── EV Sessions ──────────────────────────────────────────────────────────────
@app.get("/ev/sessions")
def get_ev_sessions(
    site_id: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Get EV charging sessions for a site."""
    site = _get_site_or_403(db, site_id, org_id)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    sessions = (
        db.query(EVSession)
        .filter(EVSession.site_id == site.id, EVSession.start_ts >= since)
        .order_by(EVSession.start_ts.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": s.id,
            "charger_id": s.charger_id,
            "start_ts": s.start_ts.isoformat(),
            "end_ts": s.end_ts.isoformat() if s.end_ts else None,
            "energy_kwh": s.energy_kwh,
            "revenue_sgd": s.revenue_sgd,
            "status": s.status,
        }
        for s in sessions
    ]


# ── Dashboard summary ────────────────────────────────────────────────────────
@app.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Aggregate KPIs for all sites in the org."""
    sites = db.query(Site).filter(Site.org_id == org_id).all()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_solar_kw = 0.0
    total_solar_kwh_today = 0.0
    total_ev_active = 0
    total_ev_kwh = 0.0
    total_ecis = 0.0
    total_co2 = 0.0
    active_anomalies = 0

    for site in sites:
        # Latest solar reading
        latest = (
            db.query(SolarReading)
            .filter(SolarReading.site_id == site.id)
            .order_by(SolarReading.ts.desc())
            .first()
        )
        if latest:
            total_solar_kw += latest.power_kw
            total_solar_kwh_today += latest.energy_kwh

        # Active EV sessions
        active = db.query(EVSession).filter(
            EVSession.site_id == site.id,
            EVSession.status == "Charging",
            EVSession.end_ts.is_(None),
        ).count()
        total_ev_active += active

        # EV kWh today
        ev_today = db.query(EVSession).filter(
            EVSession.site_id == site.id,
            EVSession.start_ts >= today_start,
            EVSession.end_ts.isnot(None),
        ).all()
        total_ev_kwh += sum(s.energy_kwh for s in ev_today)

        # ECIS credits this month
        from sqlalchemy import extract
        solar_month = db.query(SolarReading).filter(
            SolarReading.site_id == site.id,
            SolarReading.ts >= month_start,
        ).order_by(SolarReading.ts.desc()).first()
        if solar_month:
            monthly_kwh = solar_month.energy_kwh * now.day  # rough
            ecis = monthly_kwh * 0.30 * ECIS_RATE
            total_ecis += ecis
            total_co2 += monthly_kwh * CO2_FACTOR

        # Active anomalies
        anomaly_count = db.query(AnomalyLog).filter(
            AnomalyLog.site_id == site.id,
            AnomalyLog.resolved.is_(False),
        ).count()
        active_anomalies += anomaly_count

    return DashboardSummary(
        total_solar_kw=round(total_solar_kw, 2),
        total_solar_kwh_today=round(total_solar_kwh_today, 2),
        total_ev_sessions_active=total_ev_active,
        total_ev_kwh_today=round(total_ev_kwh, 2),
        ecis_credits_month=round(total_ecis, 2),
        co2_saved_kg=round(total_co2, 1),
        active_anomalies=active_anomalies,
    )


# ── Anomalies ────────────────────────────────────────────────────────────────
@app.get("/anomalies", response_model=list[AnomalyOut])
def get_anomalies(
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
    resolved: bool = Query(False),
):
    """Get anomaly log for all sites in the org."""
    site_ids = [s.id for s in db.query(Site).filter(Site.org_id == org_id).all()]
    anomalies = (
        db.query(AnomalyLog)
        .filter(AnomalyLog.site_id.in_(site_ids), AnomalyLog.resolved == resolved)
        .order_by(AnomalyLog.ts.desc())
        .limit(50)
        .all()
    )
    return [_anomaly_out(a) for a in anomalies]


@app.post("/anomalies/{anomaly_id}/resolve")
def resolve_anomaly(
    anomaly_id: int,
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Mark an anomaly as resolved."""
    site_ids = [s.id for s in db.query(Site).filter(Site.org_id == org_id).all()]
    a = db.query(AnomalyLog).filter(
        AnomalyLog.id == anomaly_id,
        AnomalyLog.site_id.in_(site_ids),
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    a.resolved = True
    db.commit()
    return {"ok": True}


# ── Evaluator: fault injection ───────────────────────────────────────────────
@app.post("/admin/inject-fault")
def api_inject_fault(
    site_id: str = Query(...),
    reduction_pct: float = Query(60.0, ge=0, le=100),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Inject a simulated fault for evaluator testing. (Sets output to X% reduction)."""
    _get_site_or_403(db, site_id, org_id)
    inject_fault(site_id, reduction_pct)
    return {"ok": True, "site_id": site_id, "reduction_pct": reduction_pct}


@app.post("/admin/clear-fault")
def api_clear_fault(
    site_id: str = Query(...),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Clear injected fault."""
    _get_site_or_403(db, site_id, org_id)
    clear_fault(site_id)
    return {"ok": True}


# ── PDF Report ───────────────────────────────────────────────────────────────
@app.get("/reports/monthly-pdf")
def download_monthly_report(
    year: int = Query(default_factory=lambda: datetime.now().year),
    month: int = Query(default_factory=lambda: datetime.now().month),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Generate and download the monthly PDF report."""
    pdf_bytes = generate_monthly_report(db, org_id, year, month)
    filename = f"SuperChargeSG_Report_{year}_{month:02d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── AI Weekly Digest ─────────────────────────────────────────────────────────
@app.get("/reports/weekly-digest")
def get_weekly_digest_preview(
    site_id: str = Query(...),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Preview AI weekly digest for a site."""
    site = _get_site_or_403(db, site_id, org_id)
    org = db.query(Organisation).filter(Organisation.id == org_id).first()
    week_end = datetime.now(timezone.utc)
    site_data = collect_weekly_site_data(db, site, org, week_end)
    digest = generate_weekly_digest(site_data)
    return {"digest": digest, "site_data": site_data}


# ── ECIS Calculator ──────────────────────────────────────────────────────────
@app.get("/ecis/calculate")
def calculate_ecis(
    site_id: str = Query(...),
    month: int = Query(default_factory=lambda: datetime.now().month),
    year: int = Query(default_factory=lambda: datetime.now().year),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Calculate ECIS export credits for a site for a given month."""
    site = _get_site_or_403(db, site_id, org_id)
    from sqlalchemy import extract
    max_energy = (
        db.query(SolarReading)
        .filter(
            SolarReading.site_id == site.id,
            extract("year", SolarReading.ts) == year,
            extract("month", SolarReading.ts) == month,
        )
        .order_by(SolarReading.energy_kwh.desc())
        .first()
    )
    solar_kwh = max_energy.energy_kwh if max_energy else 0.0
    exported_kwh = solar_kwh * 0.30
    ecis_credits = exported_kwh * ECIS_RATE
    return {
        "site_id": site_id,
        "site_name": site.name,
        "period": f"{year}-{month:02d}",
        "solar_kwh_generated": round(solar_kwh, 2),
        "estimated_exported_kwh": round(exported_kwh, 2),
        "ecis_rate_sgd_kwh": ECIS_RATE,
        "ecis_credits_sgd": round(ecis_credits, 2),
        "formula": "exported_kWh × SGD 0.218",
        "note": "Exported kWh estimated at 30% of total generation. Confirm with SP Group electricity bill.",
    }


# ── WebSocket real-time feed ─────────────────────────────────────────────────
connected_clients: dict[str, list[WebSocket]] = {}


@app.websocket("/ws/{org_id}")
async def websocket_feed(websocket: WebSocket, org_id: str):
    """
    WebSocket endpoint — pushes latest solar + EV data to connected clients.
    Clients must authenticate by sending their JWT as the first message.
    """
    await websocket.accept()
    if org_id not in connected_clients:
        connected_clients[org_id] = []
    connected_clients[org_id].append(websocket)
    logger.info("WebSocket client connected for org %s", org_id)

    try:
        while True:
            # Keep connection alive — client sends ping, server sends data
            data = await websocket.receive_text()
            if data == "ping":
                db = next(get_db())
                sites = db.query(Site).filter(Site.org_id == org_id).all()
                payload = []
                for site in sites:
                    latest = (
                        db.query(SolarReading)
                        .filter(SolarReading.site_id == site.id)
                        .order_by(SolarReading.ts.desc())
                        .first()
                    )
                    if latest:
                        payload.append({
                            "site_id": site.id,
                            "site_name": site.name,
                            "power_kw": latest.power_kw,
                            "energy_kwh": latest.energy_kwh,
                            "anomaly_flag": latest.anomaly_flag,
                            "anomaly_severity": latest.anomaly_severity,
                            "ts": latest.ts.isoformat(),
                        })
                db.close()
                await websocket.send_json({"type": "update", "data": payload})
    except WebSocketDisconnect:
        connected_clients.get(org_id, []).remove(websocket)
        logger.info("WebSocket client disconnected from org %s", org_id)


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "SuperCharge SG Smart Energy Dashboard"}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _get_site_or_403(db: Session, site_id: str, org_id: str) -> Site:
    """Retrieve a site only if it belongs to the authenticated org (403 otherwise)."""
    site = db.query(Site).filter(Site.id == site_id, Site.org_id == org_id).first()
    if not site:
        raise HTTPException(status_code=403, detail="Access denied or site not found")
    return site


def _reading_out(r: SolarReading) -> SolarReadingOut:
    return SolarReadingOut(
        ts=r.ts.isoformat(),
        power_kw=r.power_kw,
        energy_kwh=r.energy_kwh,
        irradiance=r.irradiance,
        temp_c=r.temp_c,
        expected_kw=r.expected_kw,
        performance_ratio=r.performance_ratio,
        actual_vs_expected_pct=r.actual_vs_expected_pct,
        anomaly_flag=r.anomaly_flag,
        anomaly_severity=r.anomaly_severity,
    )


def _anomaly_out(a: AnomalyLog) -> AnomalyOut:
    return AnomalyOut(
        id=a.id,
        site_id=a.site_id,
        ts=a.ts.isoformat() if a.ts else "",
        severity=a.severity,
        actual_kw=a.actual_kw,
        expected_kw=a.expected_kw,
        deviation_pct=a.deviation_pct,
        description=a.description,
        resolved=a.resolved,
    )


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=False)
