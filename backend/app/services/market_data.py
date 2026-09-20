import yfinance as yf

from app.db import database
from app.models import PriceHistory

REGION_CURRENCY = {
    "US": "USD",
    "HK": "HKD",
    "SG": "SGD",
}
CURRENCY_REGION = {currency: region for region, currency in REGION_CURRENCY.items()}


def currency_for_region(region: str) -> str:
    return REGION_CURRENCY[region]


class UnknownTickerError(Exception):
    pass


class UnsupportedMarketError(Exception):
    pass


def _reported_currency(stock: "yf.Ticker") -> str | None:
    """The currency Yahoo says the ticker trades in. history() must have been called
    first — history_metadata is populated as a side effect of it. fast_info is a
    fallback for the rare ticker whose metadata comes back empty."""
    currency = (stock.history_metadata or {}).get("currency")
    if currency:
        return currency
    try:
        return stock.fast_info.get("currency")
    except Exception:
        return None


def region_for_currency(ticker: str, currency: str | None) -> str:
    """Maps a traded currency to the app's region, rejecting anything it cannot value.
    The region is never taken from the caller: only USDSGD and HKDSGD rates exist (see
    services/fx.py), so a EUR or ARS listing has no conversion path, and trusting a
    caller-supplied region let a Vienna listing be stored as 'US'/USD — prices in euros
    converted at the USD rate, silently wrong rather than failing."""
    region = CURRENCY_REGION.get(currency or "")
    if region is None:
        raise UnsupportedMarketError(
            f"'{ticker}' trades in {currency or 'an unknown currency'}; "
            f"only {', '.join(sorted(REGION_CURRENCY.values()))} are supported"
        )
    return region


def backfill_price_history(ticker: str) -> tuple[int, str, str]:
    """One-time 5yr price backfill for a ticker that's never been tracked before.
    Returns (rows, region, currency) — the region is derived from the currency Yahoo
    reports for this ticker, taken off the same history() call, so no extra request and
    no caller gets to assert it. Raises UnknownTickerError if yfinance has no data
    (wrong suffix, delisted, typo) or UnsupportedMarketError if it trades in a currency
    the app cannot convert to SGD."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5y")

    if hist.empty:
        raise UnknownTickerError(f"No price data found for ticker '{ticker}'")

    currency = _reported_currency(stock)
    region = region_for_currency(ticker, currency)

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

    return len(rows), region, currency


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
