"""Net money flows into the 11 US sector ETFs, for the Sectors page.

An ETF creates shares when investors put net money in and redeems them when
they take it out, so a day's net flow is the change in shares outstanding times
that day's NAV. Yahoo only has today's share count, so the daily history comes
from State Street's per-fund NAV history files (date, NAV, shares outstanding,
total net assets — back to the fund's launch).

Same storage pattern as world_markets.py: sync_sector_flows() downloads and
upserts into sector_fund_days (2 years the first time, then only the last few
days) and runs in the nightly job; get_sector_flows() only reads the table.
"""

import io
import logging
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
from peewee import fn

from app.db import database
from app.models import SectorFundDay

logger = logging.getLogger(__name__)

NAV_HISTORY_URL = (
    "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/"
    "navhist-us-en-{symbol}.xlsx"
)
STALE_AFTER_DAYS = 7  # last NAV older than this -> flagged stale in the UI
INITIAL_HISTORY_DAYS = 730  # first sync: enough for YTD and 1M in any month
RESYNC_OVERLAP_DAYS = 7  # later syncs rewrite this far back to pick up late revisions
READ_WINDOW_DAYS = 400  # how much history the read functions load per fund


@dataclass(frozen=True)
class Sector:
    symbol: str
    name: str
    group: str  # "growth" | "cyclical" | "defensive" | "rates", for colouring/grouping in the UI


SECTORS: tuple[Sector, ...] = (
    Sector("XLK", "Technology", "growth"),
    Sector("XLC", "Communication Services", "growth"),
    Sector("XLY", "Consumer Discretionary", "growth"),
    Sector("XLF", "Financials", "cyclical"),
    Sector("XLI", "Industrials", "cyclical"),
    Sector("XLB", "Materials", "cyclical"),
    Sector("XLE", "Energy", "cyclical"),
    Sector("XLV", "Health Care", "defensive"),
    Sector("XLP", "Consumer Staples", "defensive"),
    Sector("XLU", "Utilities", "defensive"),
    Sector("XLRE", "Real Estate", "rates"),
)

# Trading days back for each period; "ytd" is everything since the last
# session of the previous calendar year.
PERIOD_SESSIONS = {"1d": 1, "1w": 5, "1m": 21}
PERIODS = ("1d", "1w", "1m", "ytd")


class SectorFlowsUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class FundDay:
    date: date
    nav: float
    shares: float
    total_net_assets: float


@dataclass
class PeriodStats:
    flow: float | None  # net dollars in (+) or out (-) over the period
    flow_pct: float | None  # flow as % of total net assets at the start of the period
    change: float | None  # NAV % change (price only, no dividends)


@dataclass
class SectorSnapshot:
    sector: Sector
    as_of: date | None
    nav: float | None
    total_net_assets: float | None
    periods: dict[str, PeriodStats]
    stale: bool


def _is_split(prev: FundDay, day: FundDay) -> bool:
    """A share split multiplies shares and divides NAV by the same factor, which
    would otherwise read as a huge flow. Real flows never move shares this much
    in a day while NAV moves inversely, so treat such a day as a split."""
    nav_ratio = day.nav / prev.nav
    share_ratio = day.shares / prev.shares
    return (nav_ratio < 0.7 and share_ratio > 1.3) or (nav_ratio > 1.4 and share_ratio < 0.75)


def daily_flows(days: list[FundDay]) -> list[float]:
    """Net flow for each day after the first (so one shorter than `days`, which
    must be ascending): change in shares times that day's NAV, 0 on a split."""
    return [
        0.0 if _is_split(prev, day) else (day.shares - prev.shares) * day.nav
        for prev, day in zip(days, days[1:])
    ]


def _pct(latest: float, earlier: float) -> float | None:
    return (latest / earlier - 1) * 100 if earlier else None


def _period_stats(days: list[FundDay], flows: list[float], start: int) -> PeriodStats:
    """Stats from days[start] (the session before the period) to the latest day.
    flows[i] is the flow on days[i + 1]."""
    if start < 0:
        return PeriodStats(None, None, None)
    flow = sum(flows[start:])
    base = days[start]
    return PeriodStats(
        flow=flow,
        flow_pct=flow / base.total_net_assets * 100 if base.total_net_assets else None,
        change=_pct(days[-1].nav, base.nav),
    )


def _snapshot(sector: Sector, days: list[FundDay]) -> SectorSnapshot:
    if not days:
        empty = {p: PeriodStats(None, None, None) for p in PERIODS}
        return SectorSnapshot(sector, None, None, None, empty, stale=True)

    latest = days[-1]
    flows = daily_flows(days)
    last = len(days) - 1
    periods = {p: _period_stats(days, flows, last - n) for p, n in PERIOD_SESSIONS.items()}
    prior_year = [i for i, d in enumerate(days) if d.date.year < latest.date.year]
    periods["ytd"] = _period_stats(days, flows, prior_year[-1] if prior_year else -1)

    return SectorSnapshot(
        sector=sector,
        as_of=latest.date,
        nav=latest.nav,
        total_net_assets=latest.total_net_assets,
        periods=periods,
        stale=(date.today() - latest.date).days > STALE_AFTER_DAYS,
    )


def _download(symbol: str) -> list[FundDay]:
    """The fund's full NAV history from State Street, ascending. The sheet has a
    few lines of fund info above the header row and a disclaimer below the data;
    rows whose date or numbers don't parse (those, and '-' placeholders) are dropped."""
    request = urllib.request.Request(
        NAV_HISTORY_URL.format(symbol=symbol.lower()), headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
    df = pd.read_excel(io.BytesIO(content), header=3, usecols=range(4))
    df.columns = ["date", "nav", "shares", "total_net_assets"]
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
    for col in ("nav", "shares", "total_net_assets"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna()
    df = df[(df["nav"] > 0) & (df["shares"] > 0)].sort_values("date")
    return [
        FundDay(row.date.date(), float(row.nav), float(row.shares), float(row.total_net_assets))
        for row in df.itertuples(index=False)
    ]


def sync_sector_flows() -> int:
    """Downloads each fund's NAV history and upserts the part we need: the last
    INITIAL_HISTORY_DAYS for a fund never synced, otherwise from RESYNC_OVERLAP_DAYS
    before its latest stored date. Returns the number of rows written; raises
    SectorFlowsUnavailableError if no fund could be fetched at all."""
    latest = {
        # MAX() comes back as text on SQLite, as a date on Postgres
        row.symbol: row.last if isinstance(row.last, date) else date.fromisoformat(str(row.last)[:10])
        for row in SectorFundDay.select(
            SectorFundDay.symbol, fn.MAX(SectorFundDay.date).alias("last")
        ).group_by(SectorFundDay.symbol)
    }

    rows = []
    failed = []
    for sector in SECTORS:
        try:
            days = _download(sector.symbol)
        except Exception as exc:  # network, HTTP or a changed sheet layout; skip just this fund
            logger.warning("NAV history download failed for %s: %s: %s", sector.symbol, type(exc).__name__, exc)
            failed.append(sector.symbol)
            continue
        if sector.symbol in latest:
            since = latest[sector.symbol] - timedelta(days=RESYNC_OVERLAP_DAYS)
        else:
            since = date.today() - timedelta(days=INITIAL_HISTORY_DAYS)
        rows += [
            {
                "symbol": sector.symbol,
                "date": d.date,
                "nav": d.nav,
                "shares": d.shares,
                "total_net_assets": d.total_net_assets,
            }
            for d in days
            if d.date >= since
        ]

    if len(failed) == len(SECTORS):
        raise SectorFlowsUnavailableError("Could not download NAV history for any sector ETF")

    with database.atomic():
        for i in range(0, len(rows), 500):
            SectorFundDay.insert_many(rows[i : i + 500]).on_conflict(
                conflict_target=[SectorFundDay.symbol, SectorFundDay.date],
                preserve=[SectorFundDay.nav, SectorFundDay.shares, SectorFundDay.total_net_assets],
            ).execute()

    if failed:
        logger.warning("No NAV history this sync for: %s", ", ".join(failed))
    return len(rows)


def _load_days(symbols: list[str]) -> dict[str, list[FundDay]]:
    if not SectorFundDay.select().exists():
        sync_sector_flows()

    since = date.today() - timedelta(days=READ_WINDOW_DAYS)
    out: dict[str, list[FundDay]] = {}
    query = (
        SectorFundDay.select(
            SectorFundDay.symbol,
            SectorFundDay.date,
            SectorFundDay.nav,
            SectorFundDay.shares,
            SectorFundDay.total_net_assets,
        )
        .where((SectorFundDay.date >= since) & (SectorFundDay.symbol.in_(symbols)))
        .order_by(SectorFundDay.symbol, SectorFundDay.date)
        .tuples()
    )
    for symbol, day, nav, shares, tna in query:
        out.setdefault(symbol, []).append(FundDay(day, nav, shares, tna))
    return out


def get_sector_flows() -> list[SectorSnapshot]:
    """Every sector with its latest NAV and assets, plus net flow and NAV change
    for 1D/1W/1M/YTD, read from sector_fund_days. Syncs once first if the table
    is empty (first ever load); after that, freshness comes from the nightly job
    or POST /api/sectors/flows/refresh."""
    days = _load_days([s.symbol for s in SECTORS])
    return [_snapshot(s, days.get(s.symbol, [])) for s in SECTORS]


def get_sector_flow_history(symbol: str) -> list[tuple[date, float]]:
    """(date, cumulative net flow since the start of the window) for one fund
    over the last READ_WINDOW_DAYS, for the long-run chart. Raises KeyError for
    a symbol that isn't one of SECTORS."""
    symbol = symbol.upper()
    if symbol not in {s.symbol for s in SECTORS}:
        raise KeyError(symbol)
    days = _load_days([symbol]).get(symbol, [])
    total = 0.0
    out = []
    for day, flow in zip(days[1:], daily_flows(days)):
        total += flow
        out.append((day.date, total))
    return out
