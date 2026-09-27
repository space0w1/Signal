# Research: insider purchase backtest

Offline research, separate from the Signal app. Everything under `data/` is a
re-creatable cache and is gitignored.

## Setup

```bash
cd research
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export SEC_USER_AGENT="signal-research you@example.com"   # SEC requires contact info
.venv/bin/jupyter lab insider_backtest.ipynb
```

## Files

| File | What it does |
|---|---|
| `sec.py` | Downloads the SEC's quarterly insider data sets and joins `NONDERIV_TRANS` + `SUBMISSION` + `REPORTINGOWNER` into one row per open-market purchase → `data/purchases.parquet` |
| `prices.py` | Daily prices from Yahoo, cached per ticker in `data/prices/` |
| `backtest.py` | Filters, signals, event-study backtest, variant comparison |
| `insider_backtest.ipynb` | Runs the above and shows results |

The first run with the default 2016–2026 range downloads prices for several
thousand tickers and takes a while; later runs use the cache.
