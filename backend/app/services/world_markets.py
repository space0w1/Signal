"""Headline stock market per country, for the World page's globe.

Most countries use their main local index (in local currency). Where Yahoo has
no price history for the local index, a US-listed country ETF stands in (in
USD) — `kind` tells the two apart so the UI can label it.

Daily closes are stored in world_market_prices: sync_world_markets() fetches
from Yahoo (2 years the first time, then only the last few days) and runs in
the nightly job; get_world_markets() only reads the table, so page loads never
wait on Yahoo.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from peewee import fn

from app.db import database
from app.models import WorldMarketPrice

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 7  # last close older than this -> flagged stale in the UI
INITIAL_HISTORY = "2y"  # first sync: enough for YTD and 1M in any month
RESYNC_OVERLAP_DAYS = 7  # later syncs refetch this far back to pick up late corrections
READ_WINDOW_DAYS = 400  # how much history get_world_markets() reads per market


@dataclass(frozen=True)
class Market:
    country: str
    iso_n3: str  # ISO 3166-1 numeric, matches the frontend's world-atlas country ids
    symbol: str
    index_name: str
    currency: str
    kind: str  # "index" | "etf"
    lat: float  # approximate country centre, for pointing the globe / small-country markers
    lng: float


MARKETS: tuple[Market, ...] = (
    # Americas
    Market("United States", "840", "^GSPC", "S&P 500", "USD", "index", 39.8, -98.6),
    Market("Canada", "124", "^GSPTSE", "S&P/TSX Composite", "CAD", "index", 56.1, -106.3),
    Market("Mexico", "484", "^MXX", "S&P/BMV IPC", "MXN", "index", 23.6, -102.5),
    Market("Brazil", "076", "^BVSP", "Bovespa", "BRL", "index", -14.2, -51.9),
    Market("Argentina", "032", "^MERV", "MERVAL", "ARS", "index", -38.4, -63.6),
    Market("Chile", "152", "ECH", "iShares MSCI Chile ETF", "USD", "etf", -35.7, -71.5),
    Market("Colombia", "170", "ICOLCAP.CL", "iShares MSCI COLCAP ETF", "COP", "etf", 4.6, -74.3),
    Market("Peru", "604", "EPU", "iShares MSCI Peru ETF", "USD", "etf", -9.2, -75.0),
    # Europe
    Market("United Kingdom", "826", "^FTSE", "FTSE 100", "GBP", "index", 54.0, -2.5),
    Market("Germany", "276", "^GDAXI", "DAX", "EUR", "index", 51.2, 10.4),
    Market("France", "250", "^FCHI", "CAC 40", "EUR", "index", 46.6, 2.2),
    Market("Italy", "380", "FTSEMIB.MI", "FTSE MIB", "EUR", "index", 42.8, 12.6),
    Market("Spain", "724", "^IBEX", "IBEX 35", "EUR", "index", 40.5, -3.7),
    Market("Netherlands", "528", "^AEX", "AEX", "EUR", "index", 52.1, 5.3),
    Market("Switzerland", "756", "^SSMI", "SMI", "CHF", "index", 46.8, 8.2),
    Market("Belgium", "056", "^BFX", "BEL 20", "EUR", "index", 50.5, 4.5),
    Market("Sweden", "752", "^OMX", "OMX Stockholm 30", "SEK", "index", 62.2, 17.6),
    Market("Norway", "578", "ENOR", "iShares MSCI Norway ETF", "USD", "etf", 61.4, 8.5),
    Market("Denmark", "208", "^OMXC25", "OMX Copenhagen 25", "DKK", "index", 56.0, 9.5),
    Market("Finland", "246", "^OMXH25", "OMX Helsinki 25", "EUR", "index", 64.0, 26.0),
    Market("Austria", "040", "^ATX", "ATX", "EUR", "index", 47.5, 14.6),
    Market("Poland", "616", "EPOL", "iShares MSCI Poland ETF", "USD", "etf", 51.9, 19.1),
    Market("Portugal", "620", "PSI20.LS", "PSI", "EUR", "index", 39.6, -8.0),
    Market("Greece", "300", "GD.AT", "Athens General Composite", "EUR", "index", 39.1, 22.0),
    Market("Ireland", "372", "^ISEQ", "ISEQ Overall", "EUR", "index", 53.4, -8.0),
    Market("Turkey", "792", "XU100.IS", "BIST 100", "TRY", "index", 39.0, 35.2),
    # Middle East & Africa
    Market("Israel", "376", "TA35.TA", "TA-35", "ILS", "index", 31.0, 34.9),
    Market("Saudi Arabia", "682", "KSA", "iShares MSCI Saudi Arabia ETF", "USD", "etf", 23.9, 45.1),
    Market("United Arab Emirates", "784", "UAE", "iShares MSCI UAE ETF", "USD", "etf", 23.4, 53.8),
    Market("Qatar", "634", "QAT", "iShares MSCI Qatar ETF", "USD", "etf", 25.3, 51.2),
    Market("Kuwait", "414", "KWT", "iShares MSCI Kuwait ETF", "USD", "etf", 29.3, 47.5),
    Market("South Africa", "710", "^J203.JO", "JSE All Share", "ZAR", "index", -30.6, 22.9),
    # Asia-Pacific
    Market("Japan", "392", "^N225", "Nikkei 225", "JPY", "index", 36.2, 138.3),
    Market("South Korea", "410", "^KS11", "KOSPI", "KRW", "index", 36.5, 127.9),
    Market("Taiwan", "158", "^TWII", "TAIEX", "TWD", "index", 23.7, 121.0),
    Market("China", "156", "000001.SS", "SSE Composite", "CNY", "index", 35.9, 104.2),
    Market("Hong Kong", "344", "^HSI", "Hang Seng", "HKD", "index", 22.3, 114.2),
    Market("Singapore", "702", "^STI", "Straits Times Index", "SGD", "index", 1.35, 103.8),
    Market("India", "356", "^NSEI", "Nifty 50", "INR", "index", 21.0, 78.0),
    Market("Indonesia", "360", "^JKSE", "Jakarta Composite", "IDR", "index", -2.5, 118.0),
    Market("Malaysia", "458", "^KLSE", "FTSE Bursa Malaysia KLCI", "MYR", "index", 4.2, 102.0),
    Market("Thailand", "764", "THD", "iShares MSCI Thailand ETF", "USD", "etf", 15.9, 101.0),
    Market("Philippines", "608", "EPHE", "iShares MSCI Philippines ETF", "USD", "etf", 12.9, 121.8),
    Market("Vietnam", "704", "VNM", "VanEck Vietnam ETF", "USD", "etf", 14.1, 108.3),
    Market("Australia", "036", "^AXJO", "S&P/ASX 200", "AUD", "index", -25.3, 133.8),
    Market("New Zealand", "554", "^NZ50", "S&P/NZX 50", "NZD", "index", -40.9, 174.9),
)

# Trading days back for each period. Period changes compare the latest close
# with the close that many sessions earlier.
PERIOD_SESSIONS = {"change_1w": 5, "change_1m": 21}


class WorldMarketsUnavailableError(Exception):
    pass


@dataclass
class MarketSnapshot:
    market: Market
    last_close: float | None
    as_of: date | None
    change_1d: float | None
    change_1w: float | None
    change_1m: float | None
    change_ytd: float | None
    stale: bool


def _pct(latest: float, earlier: float) -> float | None:
    return (latest / earlier - 1) * 100 if earlier else None


def _snapshot(market: Market, closes: list[tuple[date, float]]) -> MarketSnapshot:
    """closes: (date, close) ascending."""
    if not closes:
        return MarketSnapshot(market, None, None, None, None, None, None, stale=True)

    as_of, latest = closes[-1]

    def sessions_back(n: int) -> float | None:
        return _pct(latest, closes[-1 - n][1]) if len(closes) > n else None

    # YTD compares with the last close of the previous calendar year.
    prior_year = [c for d, c in closes if d.year < as_of.year]
    change_ytd = _pct(latest, prior_year[-1]) if prior_year else None

    return MarketSnapshot(
        market=market,
        last_close=latest,
        as_of=as_of,
        change_1d=sessions_back(1),
        change_1w=sessions_back(PERIOD_SESSIONS["change_1w"]),
        change_1m=sessions_back(PERIOD_SESSIONS["change_1m"]),
        change_ytd=change_ytd,
        stale=(date.today() - as_of).days > STALE_AFTER_DAYS,
    )


def _download(symbols: list[str], **kwargs) -> dict[str, pd.Series]:
    """{symbol: daily closes} for the symbols Yahoo returned data for."""
    if not symbols:
        return {}
    # auto_adjust=False: indices have no dividends, and for the ETF stand-ins a
    # price return keeps them comparable with the (price-only) indices.
    raw = yf.download(symbols, auto_adjust=False, group_by="ticker", progress=False, threads=True, **kwargs)
    out = {}
    for symbol in symbols:
        try:
            closes = raw[symbol]["Close"].dropna()
        except KeyError:
            continue
        if not closes.empty:
            out[symbol] = closes
    return out


def sync_world_markets() -> int:
    """Fetches new daily closes for every market and upserts them. Markets never
    synced get INITIAL_HISTORY; the rest only the last RESYNC_OVERLAP_DAYS before
    their latest stored date (so a close first captured intraday gets corrected).
    Returns the number of rows written; raises WorldMarketsUnavailableError if
    Yahoo returned nothing at all."""
    latest = {
        # MAX() comes back as text on SQLite, as a date on Postgres
        row.symbol: row.last if isinstance(row.last, date) else date.fromisoformat(str(row.last)[:10])
        for row in WorldMarketPrice.select(
            WorldMarketPrice.symbol, fn.MAX(WorldMarketPrice.date).alias("last")
        ).group_by(WorldMarketPrice.symbol)
    }
    symbols = [m.symbol for m in MARKETS]
    new = [s for s in symbols if s not in latest]
    known = [s for s in symbols if s in latest]

    fetched = _download(new, period=INITIAL_HISTORY)
    if known:
        start = min(latest[s] for s in known) - timedelta(days=RESYNC_OVERLAP_DAYS)
        fetched |= _download(known, start=start.isoformat())
    if not fetched:
        raise WorldMarketsUnavailableError("Yahoo returned no prices for any world market")

    rows = [
        {"symbol": symbol, "date": ts.date(), "close": float(close)}
        for symbol, closes in fetched.items()
        for ts, close in closes.items()
    ]
    with database.atomic():
        for i in range(0, len(rows), 500):
            WorldMarketPrice.insert_many(rows[i : i + 500]).on_conflict(
                conflict_target=[WorldMarketPrice.symbol, WorldMarketPrice.date],
                preserve=[WorldMarketPrice.close],
            ).execute()

    missing = sorted(set(symbols) - set(fetched))
    if missing:
        logger.warning("No Yahoo data this sync for: %s", ", ".join(missing))
    return len(rows)


def get_world_markets() -> list[MarketSnapshot]:
    """All markets with their latest stored close and 1D/1W/1M/YTD % changes,
    read from world_market_prices. Syncs once first if the table is empty (first
    ever load); after that, freshness comes from the nightly job or
    POST /api/world/markets/refresh."""
    if not WorldMarketPrice.select().exists():
        sync_world_markets()

    since = date.today() - timedelta(days=READ_WINDOW_DAYS)
    closes: dict[str, list[tuple[date, float]]] = {}
    query = (
        WorldMarketPrice.select(WorldMarketPrice.symbol, WorldMarketPrice.date, WorldMarketPrice.close)
        .where(WorldMarketPrice.date >= since)
        .order_by(WorldMarketPrice.symbol, WorldMarketPrice.date)
        .tuples()
    )
    for symbol, day, close in query:
        closes.setdefault(symbol, []).append((day, close))
    return [_snapshot(m, closes.get(m.symbol, [])) for m in MARKETS]
