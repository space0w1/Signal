from datetime import date

import yfinance as yf

from app.db import database
from app.models import FxRate

FX_PAIRS = ("USDSGD", "HKDSGD")


class FxRateUnavailableError(Exception):
    pass


def fetch_fx_rate(currency_pair: str) -> float:
    """Current spot rate for a pair like 'USDSGD' (1 unit of base -> SGD)."""
    ticker = f"{currency_pair}=X"
    info = yf.Ticker(ticker).info
    rate = info.get("regularMarketPrice")
    if rate is None:
        raise FxRateUnavailableError(f"No FX rate available for '{currency_pair}'")
    return float(rate)


def refresh_fx_rates() -> list[FxRate]:
    """Fetches today's USD->SGD and HKD->SGD rates and upserts them into
    fx_rates. Meant to be called once nightly by cron, but safe to call more
    than once a day — re-running just overwrites today's row."""
    today = date.today()
    rows = []
    for pair in FX_PAIRS:
        rate = fetch_fx_rate(pair)
        FxRate.insert(date=today, currency_pair=pair, rate=rate).on_conflict(
            conflict_target=[FxRate.date, FxRate.currency_pair],
            preserve=[FxRate.rate],
        ).execute()
        rows.append(FxRate.get(FxRate.date == today, FxRate.currency_pair == pair))
    return rows


def backfill_fx_rates() -> dict[str, int]:
    """One-time 5yr historical backfill for both tracked FX pairs, so
    past-date portfolio queries have a rate to convert with — refresh_fx_rates()
    alone only ever adds today's row. Returns rows inserted per pair."""
    rows_inserted: dict[str, int] = {}
    for pair in FX_PAIRS:
        ticker = f"{pair}=X"
        hist = yf.Ticker(ticker).history(period="5y")

        if hist.empty:
            raise FxRateUnavailableError(f"No historical FX data found for '{pair}'")

        rows = [
            {"date": index.date(), "currency_pair": pair, "rate": float(row["Close"])}
            for index, row in hist.iterrows()
        ]

        with database.atomic():
            for batch_start in range(0, len(rows), 500):
                batch = rows[batch_start : batch_start + 500]
                FxRate.insert_many(batch).on_conflict_ignore().execute()

        rows_inserted[pair] = len(rows)

    return rows_inserted
