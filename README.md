# 📈 Stock Portfolio Tracker

A self-hosted, single-page portfolio dashboard built for multi-market stock tracking (US, HK, SG). Designed for local-first deployment and secured via **Tailscale** access controls with automated nightly LLM summaries.

---

## ✨ Features

- **Multi-Currency Support**: Native display in **SGD**, automatically converting USD and HKD holdings using daily cached FX rates.
- **Dynamic Time Travel**: View full portfolio snapshots for any past date using the interactive date picker.
- **Smart Date/Ticker Constraints**: Selecting a date automatically filters available tickers to those held at the time, and vice versa.
- **Honest Backtesting**: Historical portfolio performance graphs accurately reconstruct holding periods (a stock contributes $0 prior to its purchase date).
- **Automated AI Analysis**: Daily LLM-generated market summaries for both overall portfolio concentration and individual stocks.
- **Zero-Authentication Model**: Relies entirely on Tailscale network-level security—no login forms or password managers required.

---

## 🏗️ Architecture & Stack

| Component | Choice / Technology |
| :--- | :--- |
| **Market Data & News** | `yfinance` (Prices, 5-year history, daily FX rates, news feed) |
| **Display Currency** | SGD (Converted from USD, HKD; SG stock values 1:1) |
| **Security / Access** | Tailscale network access (Single-user model, schema multi-user ready) |
| **Automation** | Nightly cron job (`06:00 - 07:00 GMT+8`, post-US market close) |

---

## 📊 Core Functional Modules

### 1. Navigation & State
* **Selector Dropdown**: Switch between **Portfolio** aggregate mode or an **Individual Ticker**.
* **Date Picker**: Time-travel to any past snapshot down to the earliest summary date.
* **Mutual Constraints**: Dropdown choices and date picker ranges automatically restrict each other based on active holding periods.

### 2. Graph & Performance Visualizer
* **Portfolio Mode**: Toggle between total aggregate SGD value (5-year view) or overlaid normalized percentage returns across all active holdings.
* **Individual Stock Mode**: Isolated historical price line for the selected ticker.
* **Cost Basis Tracking**: Cumulative running average per ticker—buying additional shares updates quantity and average cost dynamically.

### 3. AI Summary Engine
* **Cron Generation**: Runs automatically every night post-market close.
* **On-Demand Fallback**: Instantly generates and caches summaries for newly added tickers on first view.
* **Structured Output**: Concise market analysis accompanied by ranked news citations.

### 4. Interactive Panels
* **News Panel**:
    * *Portfolio Mode*: Displays all news items explicitly cited in the portfolio-level AI summary.
    * *Stock Mode*: Live passthrough of `yfinance` news for the selected ticker.
* **View Stocks Panel** *(Portfolio Mode)*: Sortable list of held positions ranked from highest to lowest PnL.
* **Modify Portfolio Modal**:
    * *Add Holding*: Enter symbol, quantity, and cost price (triggers immediate 5-year historical backfill).
    * *Remove Holding*: Soft-deletes positions to keep current views clean while preserving historical accuracy for past snapshots.

---

## ⏰ Nightly Schedule (`GMT+8`)

The system runs an automated cron process every morning between **06:00 AM and 07:00 AM SGT** (after US market close):

---

## 🗂️ Project Structure

```
.
├── backend/          # FastAPI app (yfinance, trafilatura, peewee/PostgreSQL)
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/      # settings
│   │   ├── models/    # peewee models
│   │   ├── services/  # portfolio/FX/AI-summary logic
│   │   ├── db.py
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/         # React + Vite dashboard
│   ├── src/
│   ├── nginx.conf     # serves the build + proxies /api to the backend
│   └── Dockerfile
├── k8s/              # placeholder for manifests once migrating off docker-compose
└── docker-compose.yml
```

## 🚀 Running locally

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api

For frontend-only iteration without Docker: `cd frontend && npm install && npm run dev` (proxies `/api` to `localhost:8000`).
For backend-only iteration: run `docker compose up db` to get Postgres up, then `cd backend && pip install -r requirements-dev.txt && DATABASE_URL=postgresql://signal:signal@localhost:5432/signal uvicorn app.main:app --reload` (note the `localhost` host — `db` only resolves inside the compose network).