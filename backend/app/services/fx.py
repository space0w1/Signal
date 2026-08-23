from datetime import date

import yfinance as yf

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
