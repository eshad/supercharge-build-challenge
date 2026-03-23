"""
Seed data — creates 2 client accounts and 3+ virtual sites for demo/evaluation.
Run once on first deploy: python -m backend.seed_data
"""

import os
import sys
import logging

from .database import SessionLocal, init_db
from .models import Organisation, User, Site
from .auth import hash_password

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Demo Client A — Greenfield Condo ────────────────────────────────────────
CLIENT_A = {
    "org_name": "Greenfield Condo MCST",
    "email": "admin@greenfield-condo.sg",
    "password": "SuperCharge@ClientA",
    "sites": [
        {
            "name": "Greenfield Tower 1 — Rooftop Solar",
            "lat": 1.3048, "lng": 103.8318,
            "solar_kwp": 50.0, "charger_count": 8,
        },
        {
            "name": "Greenfield Tower 2 — Car Park EV Hub",
            "lat": 1.3055, "lng": 103.8322,
            "solar_kwp": 30.0, "charger_count": 12,
        },
    ],
}

# ── Demo Client B — Sentosa Industrial Park ─────────────────────────────────
CLIENT_B = {
    "org_name": "Sentosa Industrial Park",
    "email": "energy@sentosa-industrial.sg",
    "password": "SuperCharge@ClientB",
    "sites": [
        {
            "name": "SIP Block A — Solar Farm",
            "lat": 1.2494, "lng": 103.8303,
            "solar_kwp": 120.0, "charger_count": 4,
        },
        {
            "name": "SIP Visitor Charging Bay",
            "lat": 1.2499, "lng": 103.8308,
            "solar_kwp": 20.0, "charger_count": 6,
        },
    ],
}


def seed():
    """Create demo accounts and sites in the database."""
    init_db()
    db = SessionLocal()
    try:
        for client in [CLIENT_A, CLIENT_B]:
            # Check if org already exists
            existing_user = db.query(User).filter(User.email == client["email"]).first()
            if existing_user:
                logger.info("Client already exists: %s — skipping", client["email"])
                continue

            org = Organisation(name=client["org_name"])
            db.add(org)
            db.flush()

            user = User(
                org_id=org.id,
                email=client["email"],
                hashed_password=hash_password(client["password"]),
                is_admin=True,
            )
            db.add(user)

            for site_data in client["sites"]:
                site = Site(org_id=org.id, **site_data)
                db.add(site)

            db.commit()
            logger.info("Created client: %s (%s)", client["org_name"], client["email"])

        logger.info("Seed complete. Credentials:")
        logger.info("Client A: %s / %s", CLIENT_A["email"], CLIENT_A["password"])
        logger.info("Client B: %s / %s", CLIENT_B["email"], CLIENT_B["password"])

    except Exception:
        logger.exception("Seed failed")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
