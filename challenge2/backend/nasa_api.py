"""
NASA POWER API integration — fetches real Singapore solar irradiance data.

Endpoint: https://power.larc.nasa.gov/api/temporal/monthly/point
Parameter: ALLSKY_SFC_SW_DWN (Surface irradiance kWh/m2/day)
"""

import logging
from datetime import datetime
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)

NASA_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"

# Singapore coordinates
SG_LAT = 1.3521
SG_LON = 103.8198

# Fallback monthly averages (kWh/m2/day) if API is unavailable
# Source: Knowledge Base — Singapore average 4.5–5.2 kWh/m2/day
FALLBACK_MONTHLY_IRRADIANCE = {
    1: 4.6, 2: 4.9, 3: 5.1, 4: 5.0, 5: 4.8,
    6: 4.7, 7: 4.8, 8: 4.7, 9: 4.6, 10: 4.5,
    11: 4.4, 12: 4.4,
}


@lru_cache(maxsize=1)
def get_monthly_irradiance_data() -> dict[str, float]:
    """
    Fetch 4-year average monthly irradiance for Singapore from NASA POWER.
    Returns {month_key: kWh/m2/day} e.g. {"202401": 4.8, ...}
    Cached in-process (refreshed on restart).
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude": SG_LON,
        "latitude": SG_LAT,
        "start": "2020",
        "end": "2024",
        "format": "JSON",
    }
    try:
        resp = httpx.get(NASA_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        monthly = data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
        logger.info("Fetched %d months of NASA POWER irradiance data", len(monthly))
        return monthly
    except Exception:
        logger.exception("NASA POWER API failed — using fallback irradiance values")
        return {}


def get_current_irradiance_kwh_m2_day() -> float:
    """
    Return today's expected irradiance (kWh/m2/day) for Singapore.
    Uses NASA POWER monthly average for current month.
    """
    month = datetime.utcnow().month
    nasa_data = get_monthly_irradiance_data()

    if nasa_data:
        # Find the most recent entry for this month number
        month_values = [
            v for k, v in nasa_data.items()
            if k.endswith(f"{month:02d}") and v > 0
        ]
        if month_values:
            avg = sum(month_values) / len(month_values)
            logger.debug("NASA irradiance for month %d: %.3f kWh/m2/day", month, avg)
            return avg

    # Fallback
    fallback = FALLBACK_MONTHLY_IRRADIANCE.get(month, 4.7)
    logger.debug("Using fallback irradiance for month %d: %.2f", month, fallback)
    return fallback


def expected_yield_kw(solar_kwp: float, irradiance_kwh_m2_day: float) -> float:
    """
    Calculate expected solar output in kW at a given irradiance.

    Formula: Power_kW = SystemKWp × (Irradiance_W/m²) / 1000 × PR
    Using: Irradiance_kWh/m2/day → peak W/m² approximation
    PR (Performance Ratio): 0.77 for Singapore (midpoint of 0.75–0.80)
    """
    PERFORMANCE_RATIO = 0.77
    # Convert daily kWh/m2 to instantaneous W/m2 equivalent (assume 4.5 peak hours)
    irradiance_w_m2 = (irradiance_kwh_m2_day / 4.5) * 1000
    return solar_kwp * (irradiance_w_m2 / 1000) * PERFORMANCE_RATIO
