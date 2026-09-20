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


def refresh_price_history(ticker: str) -> int:
    """Cheap nightly counterpart to backfill_price_history's one-time 5yr pull:
    fetches the last 5 trading days (covers weekends/holidays and any missed
    cron runs) and upserts, overwriting a same-day row if one already exists
    (e.g. an intraday price captured by a same-day backfill). Ticker must
    already be tracked — raises UnknownTickerError otherwise, same as
    backfill, so a caller that only knows the ticker (not its region) can
    still refresh it."""
    existing = PriceHistory.select().where(PriceHistory.ticker == ticker).first()
    if existing is None:
        raise UnknownTickerError(f"'{ticker}' has no price history yet — backfill it first")
    currency = existing.currency

    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d")

    if hist.empty:
        raise UnknownTickerError(f"No price data found for ticker '{ticker}'")

    rows_written = 0
    for index, row in hist.iterrows():
        PriceHistory.insert(
            ticker=ticker, date=index.date(), close_price=float(row["Close"]), currency=currency
        ).on_conflict(
            conflict_target=[PriceHistory.ticker, PriceHistory.date],
            preserve=[PriceHistory.close_price],
        ).execute()
        rows_written += 1

    return rows_written
