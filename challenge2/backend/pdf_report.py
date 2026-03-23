"""
Monthly PDF Report Generator — branded SuperCharge SG report.
Uses ReportLab.
"""

import io
import logging
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from sqlalchemy.orm import Session

from .models import Site, SolarReading, EVSession, AnomalyLog, Organisation

logger = logging.getLogger(__name__)

# Brand colours
BRAND_DARK = colors.HexColor("#0D2137")   # Dark navy
BRAND_TEAL = colors.HexColor("#00B5CC")   # Teal accent
BRAND_GOLD = colors.HexColor("#F5A623")   # Gold highlight
WHITE = colors.white
LIGHT_GREY = colors.HexColor("#F5F7FA")

ECIS_RATE = 0.218  # SGD/kWh
CO2_FACTOR = 0.4085  # kg CO2/kWh


def generate_monthly_report(
    db: Session,
    org_id: str,
    year: int,
    month: int,
) -> bytes:
    """
    Generate a branded monthly PDF report for an organisation.
    Returns PDF bytes.
    """
    org = db.query(Organisation).filter(Organisation.id == org_id).first()
    if not org:
        raise ValueError("Organisation not found")

    sites = db.query(Site).filter(Site.org_id == org_id).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Header ──────────────────────────────────────────────────────────────
    header_style = ParagraphStyle(
        "header",
        parent=styles["Normal"],
        fontSize=22,
        textColor=WHITE,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    sub_style = ParagraphStyle(
        "sub",
        parent=styles["Normal"],
        fontSize=11,
        textColor=WHITE,
        alignment=TA_CENTER,
    )

    header_table = Table(
        [[
            Paragraph("⚡ SuperCharge SG", header_style),
            Paragraph(f"Monthly Energy Report\n{datetime(year, month, 1).strftime('%B %Y')}", sub_style),
        ]],
        colWidths=[9 * cm, 8 * cm],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Client info ──────────────────────────────────────────────────────────
    client_style = ParagraphStyle("client", fontSize=13, fontName="Helvetica-Bold", textColor=BRAND_DARK)
    elements.append(Paragraph(f"Client: {org.name}", client_style))
    elements.append(Paragraph(f"Report Period: {datetime(year, month, 1).strftime('%d %B %Y')} — {_last_day(year, month):02d} {datetime(year, month, 1).strftime('%B %Y')}", styles["Normal"]))
    elements.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}", styles["Normal"]))
    elements.append(HRFlowable(width="100%", thickness=2, color=BRAND_TEAL))
    elements.append(Spacer(1, 0.3 * cm))

    # ── Site Summary Table ───────────────────────────────────────────────────
    elements.append(Paragraph("Site Performance Summary", ParagraphStyle("h2", fontSize=14, fontName="Helvetica-Bold", textColor=BRAND_DARK)))
    elements.append(Spacer(1, 0.2 * cm))

    total_solar_kwh = 0
    total_ev_kwh = 0
    total_ecis = 0
    total_revenue = 0
    total_co2 = 0

    site_data = [["Site", "Solar (kWh)", "EV Sessions", "EV Energy (kWh)", "Revenue (SGD)", "ECIS Credits (SGD)"]]

    for site in sites:
        solar_kwh = _get_solar_kwh(db, site.id, year, month)
        ev_kwh, ev_revenue, ev_count = _get_ev_stats(db, site.id, year, month)
        exported_kwh = solar_kwh * 0.30  # 30% export estimate
        ecis = round(exported_kwh * ECIS_RATE, 2)
        co2 = round(solar_kwh * CO2_FACTOR, 1)

        total_solar_kwh += solar_kwh
        total_ev_kwh += ev_kwh
        total_ecis += ecis
        total_revenue += ev_revenue
        total_co2 += co2

        site_data.append([
            site.name,
            f"{solar_kwh:.1f}",
            str(ev_count),
            f"{ev_kwh:.1f}",
            f"${ev_revenue:.2f}",
            f"${ecis:.2f}",
        ])

    site_data.append([
        "TOTAL",
        f"{total_solar_kwh:.1f}",
        "—",
        f"{total_ev_kwh:.1f}",
        f"${total_revenue:.2f}",
        f"${total_ecis:.2f}",
    ])

    site_table = Table(site_data, colWidths=[4.5 * cm, 2.5 * cm, 2 * cm, 3 * cm, 2.8 * cm, 3 * cm])
    site_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, -1), (-1, -1), BRAND_TEAL),
        ("TEXTCOLOR", (0, -1), (-1, -1), WHITE),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [LIGHT_GREY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(site_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── KPI summary boxes ────────────────────────────────────────────────────
    elements.append(Paragraph("Key Performance Indicators", ParagraphStyle("h2", fontSize=14, fontName="Helvetica-Bold", textColor=BRAND_DARK)))
    elements.append(Spacer(1, 0.2 * cm))

    kpi_data = [[
        _kpi_box("Solar Generated", f"{total_solar_kwh:.0f} kWh"),
        _kpi_box("ECIS Credits Earned", f"SGD {total_ecis:.2f}"),
        _kpi_box("CO₂ Avoided", f"{total_co2:.0f} kg"),
        _kpi_box("EV Revenue", f"SGD {total_revenue:.2f}"),
    ]]
    kpi_table = Table(kpi_data, colWidths=[4.2 * cm, 4.2 * cm, 4.2 * cm, 4.2 * cm])
    kpi_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── ECIS Credit Calculation ──────────────────────────────────────────────
    elements.append(Paragraph("ECIS Export Credit Calculation", ParagraphStyle("h2", fontSize=14, fontName="Helvetica-Bold", textColor=BRAND_DARK)))
    elements.append(Spacer(1, 0.2 * cm))

    exported_total = total_solar_kwh * 0.30
    ecis_calc_data = [
        ["Parameter", "Value", "Notes"],
        ["Total Solar Generation", f"{total_solar_kwh:.1f} kWh", "Sum of all sites"],
        ["Estimated Export (30%)", f"{exported_total:.1f} kWh", "Typical SG residential export ratio"],
        ["ECIS Export Rate", "SGD 0.218/kWh", "Enhanced Central Intermediary Scheme baseline"],
        ["ECIS Credits Earned", f"SGD {total_ecis:.2f}", f"{exported_total:.1f} × 0.218"],
    ]
    ecis_table = Table(ecis_calc_data, colWidths=[6 * cm, 4 * cm, 7.8 * cm])
    ecis_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GREY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(ecis_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Anomaly Log ──────────────────────────────────────────────────────────
    anomalies = _get_anomaly_log(db, [s.id for s in sites], year, month)
    elements.append(Paragraph("Anomaly Log", ParagraphStyle("h2", fontSize=14, fontName="Helvetica-Bold", textColor=BRAND_DARK)))
    elements.append(Spacer(1, 0.2 * cm))

    if anomalies:
        anom_data = [["Timestamp", "Site", "Severity", "Actual (kW)", "Expected (kW)", "Deviation"]]
        for a in anomalies:
            site_name = next((s.name for s in sites if s.id == a.site_id), "Unknown")
            anom_data.append([
                a.ts.strftime("%d/%m %H:%M") if a.ts else "—",
                site_name,
                a.severity,
                f"{a.actual_kw:.2f}" if a.actual_kw else "—",
                f"{a.expected_kw:.2f}" if a.expected_kw else "—",
                f"{a.deviation_pct:.1f}%" if a.deviation_pct else "—",
            ])
        anom_table = Table(anom_data, colWidths=[3 * cm, 4 * cm, 2.5 * cm, 2.8 * cm, 2.8 * cm, 2.7 * cm])
        anom_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.red),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GREY, WHITE]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(anom_table)
    else:
        elements.append(Paragraph("✅ No anomalies detected this month.", styles["Normal"]))

    elements.append(Spacer(1, 0.5 * cm))

    # ── Footer ───────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=BRAND_TEAL))
    footer_style = ParagraphStyle("footer", fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    elements.append(Paragraph(
        "SuperCharge SG — supercharge.sg — support@supercharge.sg | "
        "LTA-Licensed Electric Vehicle Charging Operator (EVCO) | TR25 Compliant",
        footer_style,
    ))
    elements.append(Paragraph(
        "This report is auto-generated. ECIS credits are indicative — confirm with SP Group bills.",
        footer_style,
    ))

    doc.build(elements)
    return buffer.getvalue()


def _kpi_box(label: str, value: str) -> Table:
    """Build a KPI display box."""
    t = Table([[Paragraph(value, ParagraphStyle("kv", fontSize=16, fontName="Helvetica-Bold", textColor=BRAND_DARK, alignment=TA_CENTER))],
               [Paragraph(label, ParagraphStyle("kl", fontSize=8, textColor=colors.grey, alignment=TA_CENTER))]])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("BOX", (0, 0), (-1, -1), 1, BRAND_TEAL),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return t


def _get_solar_kwh(db: Session, site_id: str, year: int, month: int) -> float:
    from sqlalchemy import func, extract
    result = db.query(func.max(SolarReading.energy_kwh)).filter(
        SolarReading.site_id == site_id,
        extract("year", SolarReading.ts) == year,
        extract("month", SolarReading.ts) == month,
    ).scalar()
    return result or 0.0


def _get_ev_stats(db: Session, site_id: str, year: int, month: int):
    from sqlalchemy import func, extract
    sessions = db.query(EVSession).filter(
        EVSession.site_id == site_id,
        EVSession.end_ts.isnot(None),
        extract("year", EVSession.start_ts) == year,
        extract("month", EVSession.start_ts) == month,
    ).all()
    kwh = sum(s.energy_kwh for s in sessions)
    revenue = sum(s.revenue_sgd for s in sessions)
    return round(kwh, 2), round(revenue, 2), len(sessions)


def _get_anomaly_log(db: Session, site_ids: list, year: int, month: int) -> list:
    from sqlalchemy import extract
    return db.query(AnomalyLog).filter(
        AnomalyLog.site_id.in_(site_ids),
        extract("year", AnomalyLog.ts) == year,
        extract("month", AnomalyLog.ts) == month,
    ).order_by(AnomalyLog.ts.desc()).limit(20).all()


def _last_day(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]
