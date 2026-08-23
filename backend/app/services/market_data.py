import yfinance as yf

from app.db import database
from app.models import PriceHistory

REGION_CURRENCY = {
    "US": "USD",
    "HK": "HKD",
    "SG": "SGD",
}


def currency_for_region(region: str) -> str:
    return REGION_CURRENCY[region]


class UnknownTickerError(Exception):
    pass


def backfill_price_history(ticker: str, currency: str) -> int:
    """One-time 5yr price backfill for a ticker that's never been tracked before.
    Returns the number of rows inserted. Raises UnknownTickerError if yfinance
    has no data for the ticker (e.g. wrong exchange suffix, delisted, typo)."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5y")

    if hist.empty:
        raise UnknownTickerError(f"No price data found for ticker '{ticker}'")

    rows = [
        {
            "ticker": ticker,
            "date": index.date(),
            "close_price": float(row["Close"]),
            "currency": currency,
        }
        for index, row in hist.iterrows()
    ]

    with database.atomic():
        for batch_start in range(0, len(rows), 500):
            batch = rows[batch_start : batch_start + 500]
            PriceHistory.insert_many(batch).on_conflict_ignore().execute()

    return len(rows)
