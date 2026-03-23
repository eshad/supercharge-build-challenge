# Challenge 2 — Smart Energy Dashboard SaaS
**SuperCharge SG Build Challenge 2026 | Mehadi Hasan**

## Overview

Real-time solar + EV monitoring dashboard for SuperCharge SG enterprise clients.
Multi-tenant, AI anomaly detection, ECIS credit tracking, auto PDF reports, AI weekly digests.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  DATA SIMULATION LAYER                                  │
│  Python APScheduler → solar/EV telemetry every 30s     │
│  NASA POWER API → real Singapore irradiance baseline   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  BACKEND (FastAPI)                                      │
│  SQLAlchemy ORM → SQLite (dev) / PostgreSQL (prod)     │
│  JWT multi-tenant auth (org-scoped queries)            │
│  WebSocket → real-time dashboard updates               │
│  REST endpoints: /sites, /solar, /ev, /anomalies       │
│  APScheduler: simulation + weekly digest jobs          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  FRONTEND (React + Vite + Tailwind + Recharts)          │
│  Login (JWT stored in localStorage)                    │
│  Solar view: live chart, fault injection, KPIs         │
│  EV view: session table, bar chart, revenue           │
│  Anomaly panel: ML-flagged alerts, resolve button      │
│  ECIS tracker: credit calculation with formula        │
│  Reports: PDF download + AI weekly digest preview      │
└─────────────────────────────────────────────────────────┘
```

## Data Model

```sql
organisations (id, name, created_at)
users (id, org_id, email, hashed_password, is_admin)
sites (id, org_id, name, lat, lng, solar_kwp, charger_count)
solar_readings (id, site_id, ts, power_kw, energy_kwh, irradiance,
                temp_c, expected_kw, performance_ratio,
                actual_vs_expected_pct, anomaly_flag, anomaly_severity)
ev_sessions (id, site_id, charger_id, start_ts, end_ts,
             energy_kwh, revenue_sgd, status)
anomaly_log (id, site_id, ts, severity, actual_kw, expected_kw,
             deviation_pct, description, resolved)
```

Multi-tenant isolation: Every DB query is scoped by `org_id` from JWT payload.
Row-level: `WHERE site_id IN (SELECT id FROM sites WHERE org_id = :current_org_id)`

## ML Anomaly Detection

**Model**: Isolation Forest (scikit-learn)

**Features used**:
- `performance_ratio` — actual/expected output ratio
- `actual_vs_expected_pct` — % deviation from irradiance-corrected expectation
- `temp_c` — panel temperature (higher temp = expected lower output)
- `irradiance` — instantaneous solar irradiance (kWh/m²)

**Training**: Fitted on existing solar_readings at startup. If <10 samples, falls back to rule-based threshold detection.

**Contamination**: 5% (expected anomaly rate in simulation)

**Thresholds**:
- `score < -0.10` → WARNING
- `score < -0.30` → CRITICAL
- `actual_vs_expected_pct < -15%` → always flagged (rule-based, overrides ML)

**False positive rate**: ~5% by design (contamination=0.05). Production deployment should tune contamination based on historical clean data.

**Evaluator test**: Use the "Inject Fault" button in the Solar view UI, or POST to `/admin/inject-fault?site_id=X&reduction_pct=60`. This sets the simulator to output 40% of expected power, triggering CRITICAL anomaly within one data refresh cycle (≤30 seconds).

## NASA POWER API Integration

Endpoint: `https://power.larc.nasa.gov/api/temporal/monthly/point`
Parameter: `ALLSKY_SFC_SW_DWN` (surface irradiance kWh/m2/day)
Coordinates: Singapore — lat=1.3521, lon=103.8198

Expected yield formula:
```
Irradiance_W_m2 = (kWh_m2_day / 4.5) × 1000   # Peak sun hours = 4.5
Expected_kW = System_kWp × (Irradiance_W_m2 / 1000) × 0.77   # PR = 0.77
```

Fallback: Monthly average irradiance hardcoded if API unavailable (4.4–5.1 kWh/m2/day by month).

## ECIS Credit Calculation

```
exported_kWh = total_solar_kWh × 0.30   # 30% residential export rate (SG typical)
ecis_credits_SGD = exported_kWh × 0.218  # Enhanced Central Intermediary Scheme rate
```

Rate: SGD 0.218/kWh (baseline — verify current rate with SP Group as it changes quarterly).

## Demo Accounts

| Client | Email | Password | Sites |
|--------|-------|----------|-------|
| Client A — Greenfield Condo MCST | admin@greenfield-condo.sg | SuperCharge@ClientA | Greenfield Tower 1 (50kWp) + Tower 2 (30kWp) |
| Client B — Sentosa Industrial Park | energy@sentosa-industrial.sg | SuperCharge@ClientB | SIP Block A (120kWp) + Visitor Bay (20kWp) |

**Multi-tenant isolation verification**:
1. Login as Client A → see only Greenfield sites
2. Login as Client B → see only Sentosa sites
3. Take Client A's JWT → call `/solar/readings?site_id=<ClientB_site_id>` → expect 403

## Deployment

### Option A: Docker Compose (recommended for local/VPS)
```bash
cd challenge2

# Fill in required env vars
cp .env.example .env
# edit .env

docker-compose up -d
# Dashboard: http://localhost:3000
# API: http://localhost:8001/docs
```

### Option B: Railway.app (free tier)
```bash
# Deploy backend
cd challenge2/backend
railway init
railway up

# Set env vars in Railway dashboard

# Deploy frontend
cd challenge2/frontend
# Set VITE_API_URL to your Railway backend URL
railway init
railway up
```

### Option C: Render.com
1. Create a new Web Service → connect GitHub repo
2. Build command: `pip install -r backend/requirements.txt`
3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables

## Environment Variables

```
SECRET_KEY=your-jwt-secret-key-here
OPENAI_API_KEY=sk-...
DATABASE_URL=sqlite:///./supercharge_dashboard.db  # or postgresql://...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your-app-password
```

## API Documentation

FastAPI auto-generates interactive docs at `/docs` (Swagger UI) and `/redoc`.

Key endpoints:
- `POST /auth/login` — get JWT token
- `GET /sites` — list org sites
- `GET /solar/readings?site_id=X&hours=24` — solar time series
- `GET /dashboard/summary` — aggregate KPIs
- `GET /anomalies` — anomaly log
- `POST /admin/inject-fault?site_id=X` — inject fault for evaluator testing
- `GET /reports/monthly-pdf?year=2026&month=3` — download PDF
- `GET /reports/weekly-digest?site_id=X` — AI digest preview
- `GET /ecis/calculate?site_id=X` — ECIS credit calculation
- `WS /ws/{org_id}` — real-time WebSocket feed (send "ping", receive site updates)
