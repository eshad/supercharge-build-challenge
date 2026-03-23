"""
AI Weekly Digest — generates plain-English energy summary per client via LLM.
Auto-sent by email on a scheduled basis.
"""

import os
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from openai import OpenAI
from sqlalchemy.orm import Session

from .models import Organisation, Site, SolarReading, EVSession, AnomalyLog
from .database import SessionLocal

logger = logging.getLogger(__name__)

ECIS_RATE = 0.218
CO2_FACTOR = 0.4085


def generate_weekly_digest(site_data: dict) -> str:
    """
    Generate a plain-English weekly energy summary using GPT-4o-mini.
    site_data: dict with client_name, site_name, week_end, solar_kwh,
               expected_kwh, ev_sessions, ev_kwh, ecis_credits, anomaly_count,
               anomaly_details, co2_kg
    """
    oai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    prompt = f"""You are the energy reporting assistant for SuperCharge SG.

Write a professional weekly energy digest for client: {site_data['client_name']}
Site: {site_data['site_name']} | Week ending: {site_data['week_end']}

DATA:
- Solar generated: {site_data['solar_kwh']:.1f} kWh (expected: {site_data['expected_kwh']:.1f} kWh)
- EV sessions: {site_data['ev_sessions']} sessions, {site_data['ev_kwh']:.1f} kWh delivered
- ECIS credits earned: SGD {site_data['ecis_credits']:.2f}
- Anomalies detected: {site_data['anomaly_count']} ({site_data['anomaly_details']})
- CO2 saved: {site_data['co2_kg']:.1f} kg

Write 3 short paragraphs:
1. Summary performance vs expectation
2. Anomalies and recommended actions
3. Savings highlight (ECIS + CO2)

Keep it under 150 words. Plain English. No jargon. Professional tone. No bullet points."""

    try:
        resp = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.5,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        logger.exception("LLM digest generation failed")
        return _fallback_digest(site_data)


def _fallback_digest(site_data: dict) -> str:
    """Fallback template if LLM is unavailable."""
    perf_pct = (site_data['solar_kwh'] / max(site_data['expected_kwh'], 1)) * 100
    return (
        f"Week ending {site_data['week_end']} — {site_data['site_name']}\n\n"
        f"Your site generated {site_data['solar_kwh']:.1f} kWh of solar energy this week, "
        f"achieving {perf_pct:.0f}% of expected output. "
        f"{site_data['ev_sessions']} EV charging sessions delivered {site_data['ev_kwh']:.1f} kWh.\n\n"
        f"{'No anomalies detected.' if site_data['anomaly_count'] == 0 else f\"{site_data['anomaly_count']} anomaly(s) detected: {site_data['anomaly_details']}. Please contact support.\"}\n\n"
        f"ECIS export credits earned: SGD {site_data['ecis_credits']:.2f}. "
        f"CO₂ avoided: {site_data['co2_kg']:.1f} kg. Thank you for choosing SuperCharge SG."
    )


def collect_weekly_site_data(db: Session, site: Site, org: Organisation, week_end: datetime) -> dict:
    """Collect weekly statistics for a site."""
    from sqlalchemy import extract, func
    week_start = week_end - timedelta(days=7)

    # Solar generation
    readings = db.query(SolarReading).filter(
        SolarReading.site_id == site.id,
        SolarReading.ts >= week_start,
        SolarReading.ts <= week_end,
    ).all()

    if readings:
        max_energy = max(r.energy_kwh for r in readings)
        avg_expected_kw = sum(r.expected_kw for r in readings) / len(readings)
        hours = 12 * 7  # 12 peak hours/day x 7 days
        expected_kwh = avg_expected_kw * hours
    else:
        max_energy = 0.0
        expected_kwh = site.solar_kwp * 4.7 * 7 * 0.77  # Rough estimate

    # EV sessions
    sessions = db.query(EVSession).filter(
        EVSession.site_id == site.id,
        EVSession.start_ts >= week_start,
        EVSession.start_ts <= week_end,
        EVSession.end_ts.isnot(None),
    ).all()

    ev_kwh = sum(s.energy_kwh for s in sessions)

    # Anomalies
    anomalies = db.query(AnomalyLog).filter(
        AnomalyLog.site_id == site.id,
        AnomalyLog.ts >= week_start,
        AnomalyLog.ts <= week_end,
    ).all()

    anomaly_details = (
        ", ".join(set(a.severity for a in anomalies)) if anomalies else "None"
    )

    exported_kwh = max_energy * 0.30
    ecis_credits = exported_kwh * ECIS_RATE
    co2_kg = max_energy * CO2_FACTOR

    return {
        "client_name": org.name,
        "site_name": site.name,
        "week_end": week_end.strftime("%d %b %Y"),
        "solar_kwh": round(max_energy, 1),
        "expected_kwh": round(expected_kwh, 1),
        "ev_sessions": len(sessions),
        "ev_kwh": round(ev_kwh, 1),
        "ecis_credits": round(ecis_credits, 2),
        "anomaly_count": len(anomalies),
        "anomaly_details": anomaly_details,
        "co2_kg": round(co2_kg, 1),
    }


def send_weekly_digest_email(to_email: str, org_name: str, digest_text: str) -> bool:
    """Send digest via SMTP."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    if not smtp_host or not smtp_user:
        logger.info("SMTP not configured — digest not emailed to %s", to_email)
        logger.info("DIGEST CONTENT:\n%s", digest_text)
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = f"Your Weekly Energy Report — SuperCharge SG"

    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto">
<div style="background:#0D2137;padding:20px;text-align:center">
  <h1 style="color:white;margin:0">⚡ SuperCharge SG</h1>
  <p style="color:#00B5CC;margin:5px 0">Weekly Energy Report</p>
</div>
<div style="padding:24px;background:#f9f9f9">
  <p>Dear {org_name} Team,</p>
  <p>Here is your weekly energy performance summary:</p>
  <div style="background:white;padding:16px;border-left:4px solid #00B5CC;border-radius:4px">
    <p style="white-space:pre-line">{digest_text}</p>
  </div>
  <p style="margin-top:24px;color:#666;font-size:12px">
    This report is auto-generated by SuperCharge SG's Smart Energy Dashboard.<br>
    Questions? Contact us at support@supercharge.sg
  </p>
</div>
<div style="background:#0D2137;padding:12px;text-align:center">
  <p style="color:#888;font-size:11px;margin:0">
    SuperCharge SG — supercharge.sg — LTA-Licensed EVCO
  </p>
</div>
</body></html>"""

    msg.attach(MIMEText(digest_text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Weekly digest emailed to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send digest email to %s", to_email)
        return False


def run_weekly_digests() -> None:
    """
    Generate and send weekly digests for all organisations.
    Called by scheduler every Monday 08:00 SGT.
    """
    db = SessionLocal()
    try:
        orgs = db.query(Organisation).all()
        week_end = datetime.now(timezone.utc)

        for org in orgs:
            sites = db.query(Site).filter(Site.org_id == org.id).all()
            for site in sites:
                site_data = collect_weekly_site_data(db, site, org, week_end)
                digest = generate_weekly_digest(site_data)

                # Send to all org users
                from .models import User
                users = db.query(User).filter(User.org_id == org.id).all()
                for user in users:
                    send_weekly_digest_email(user.email, org.name, digest)

        logger.info("Weekly digests sent for %d organisations", len(orgs))
    except Exception:
        logger.exception("Weekly digest job failed")
    finally:
        db.close()
