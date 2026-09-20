from dataclasses import dataclass
from datetime import date, timedelta

from app.models import FxRate, Holding, PriceHistory, Transaction
from app.services.holdings import get_default_user

RANGE_YEARS = 5


@dataclass
class DailyPoint:
    date: date
    value_sgd: float
    cost_sgd: float
    unrealized_pnl: float
    realized_pnl_sgd: float


@dataclass
class DailyPortfolioPoint:
    date: date
    total_value_sgd: float = 0.0
    total_cost_sgd: float = 0.0
    total_unrealized_pnl_amount: float = 0.0
    total_realized_pnl_sgd: float = 0.0


@dataclass
class OverlayPoint:
    date: date
    pnl_pct: float


def _range_start(as_of: date) -> date:
    return as_of - timedelta(days=365 * RANGE_YEARS)


def _build_axis(tickers: list[str], start: date, end: date) -> list[date]:
    """The trading-day calendar to plot against — the union of every date any
    involved ticker has a price for, not a per-ticker or fixed calendar, so a
    holiday on one exchange (e.g. HK) doesn't create a false dip in the total
    just because another market (e.g. US) was open that day."""
    rows = (
        PriceHistory.select(PriceHistory.date)
        .where(PriceHistory.ticker.in_(tickers), PriceHistory.date >= start, PriceHistory.date <= end)
        .distinct()
        .order_by(PriceHistory.date)
    )
    return [row.date for row in rows]


def _holding_daily_series(holding: Holding, axis: list[date], end: date) -> list[DailyPoint]:
    """Walks the shared axis once, advancing price/fx/transaction pointers as
    needed (carrying forward the last known price/fx rate between trading
    days) — a single pass per holding instead of a query per day."""
    prices = list(
        PriceHistory.select()
        .where(PriceHistory.ticker == holding.ticker, PriceHistory.date <= end)
        .order_by(PriceHistory.date)
    )
    transactions = list(
        Transaction.select()
        .where(
            Transaction.holding == holding,
            Transaction.transaction_date >= holding.date_added,
            Transaction.transaction_date <= end,
        )
        .order_by(Transaction.transaction_date, Transaction.id)
    )
    fx_rates: list[FxRate] = []
    if holding.currency != "SGD":
        pair = f"{holding.currency}SGD"
        fx_rates = list(
            FxRate.select()
            .where(FxRate.currency_pair == pair, FxRate.date <= end)
            .order_by(FxRate.date)
        )

    points: list[DailyPoint] = []
    price_idx = txn_idx = fx_idx = 0
    current_price: float | None = None
    current_fx: float | None = 1.0 if holding.currency == "SGD" else None
    quantity = cost_basis = realized_pnl = 0.0

    for day in axis:
        while price_idx < len(prices) and prices[price_idx].date <= day:
            current_price = prices[price_idx].close_price
            price_idx += 1
        while fx_idx < len(fx_rates) and fx_rates[fx_idx].date <= day:
            current_fx = fx_rates[fx_idx].rate
            fx_idx += 1
        while txn_idx < len(transactions) and transactions[txn_idx].transaction_date <= day:
            txn = transactions[txn_idx]
            if txn.type == "buy":
                quantity += txn.quantity
                cost_basis += txn.quantity * txn.price
            else:
                avg_cost = (cost_basis / quantity) if quantity > 0 else 0.0
                sold_qty = min(txn.quantity, quantity)
                realized_pnl += sold_qty * (txn.price - avg_cost)
                quantity -= sold_qty
                cost_basis -= sold_qty * avg_cost
                if quantity < 1e-9:
                    quantity = 0.0
                    cost_basis = 0.0
            txn_idx += 1

        if current_price is None or current_fx is None:
            continue  # no price/fx data this far back for this ticker yet

        value_sgd = quantity * current_price * current_fx
        cost_sgd = cost_basis * current_fx
        points.append(
            DailyPoint(
                date=day,
                value_sgd=value_sgd,
                cost_sgd=cost_sgd,
                unrealized_pnl=value_sgd - cost_sgd,
                realized_pnl_sgd=realized_pnl * current_fx,
            )
        )

    return points


def get_portfolio_value_series(as_of: date) -> list[DailyPortfolioPoint]:
    """Total portfolio value/PnL over the last 5yr, reconstructed day by day.
    Includes every holding the user has ever had (not just currently active
    ones) — a closed-out position still really contributed value while it
    was held, and its own quantity naturally goes to zero outside the window
    it was owned, so no separate active-window filter is needed here."""
    user = get_default_user()
    start = _range_start(as_of)
    holdings = list(Holding.select().where(Holding.user == user))
    if not holdings:
        return []

    axis = _build_axis([h.ticker for h in holdings], start, as_of)
    totals = {d: DailyPortfolioPoint(date=d) for d in axis}

    for holding in holdings:
        for point in _holding_daily_series(holding, axis, as_of):
            agg = totals[point.date]
            agg.total_value_sgd += point.value_sgd
            agg.total_cost_sgd += point.cost_sgd
            agg.total_unrealized_pnl_amount += point.unrealized_pnl
            agg.total_realized_pnl_sgd += point.realized_pnl_sgd

    return [totals[d] for d in axis]


@dataclass
class StockGraphPoint:
    date: date
    price: float
    currency: str
    pnl_pct: float | None  # None if this ticker isn't a currently-active holding
    pnl_amount_sgd: float | None  # absolute unrealized PnL in SGD, matching every other PnL figure in the app


def get_stock_graph_series(ticker: str, as_of: date) -> list[StockGraphPoint]:
    """5yr close-price line for a single ticker, in its native currency, plus
    unrealized PnL % and absolute $ (SGD) for each day it's been held (None
    outside that window, or entirely if the ticker isn't a currently-active
    holding) — lets the frontend toggle between raw price and PnL% without a
    second endpoint."""
    start = _range_start(as_of)
    prices = list(
        PriceHistory.select()
        .where(PriceHistory.ticker == ticker, PriceHistory.date >= start, PriceHistory.date <= as_of)
        .order_by(PriceHistory.date)
    )

    user = get_default_user()
    holding = Holding.get_or_none(Holding.user == user, Holding.ticker == ticker, Holding.is_active == True)  # noqa: E712

    pnl_pct_by_date: dict[date, float] = {}
    pnl_amount_by_date: dict[date, float] = {}
    if holding is not None:
        clamp_start = max(start, holding.date_added)
        axis = _build_axis([ticker], clamp_start, as_of)

        # The clamp yields an empty range in two very different situations, and only
        # one of them deserves a fallback:
        #
        #   a) held by as_of, but no trading day since — bought on a Saturday, and
        #      Monday's close has not published yet. Worth valuing: the carried-forward
        #      last close is a real price and the purchase still applies. Without this
        #      every pnl_pct stays None and the UI reads "not currently held".
        #   b) as_of predates date_added — the position did not exist yet. pnl_pct MUST
        #      stay None here, or picking a stock and then an earlier date reports a
        #      fabricated 0.00% return on something never owned.
        #
        # clamp_start <= as_of distinguishes them.
        if not axis and clamp_start <= as_of:
            axis = [as_of]

        # Key the fallback point to the latest close's own date, not as_of: the points
        # below are built from `prices`, so a key of as_of would never be looked up.
        fallback_date = prices[-1].date if (len(axis) == 1 and axis[0] == as_of and prices) else None
        for p in _holding_daily_series(holding, axis, as_of):
            key = fallback_date or p.date
            pnl_pct_by_date[key] = (p.unrealized_pnl / p.cost_sgd * 100) if p.cost_sgd else 0.0
            pnl_amount_by_date[key] = p.unrealized_pnl

    return [
        StockGraphPoint(
            date=p.date,
            price=p.close_price,
            currency=p.currency,
            pnl_pct=pnl_pct_by_date.get(p.date),
            pnl_amount_sgd=pnl_amount_by_date.get(p.date),
        )
        for p in prices
    ]


def get_portfolio_pnl_pct_series(as_of: date) -> list[OverlayPoint]:
    """Overall portfolio unrealized PnL % over time — total_unrealized_pnl /
    total_cost from get_portfolio_value_series, just normalized to a
    percentage so it can be plotted alongside the per-holding overlay lines
    as a single blended 'how is the whole portfolio doing' line."""
    return [
        OverlayPoint(
            date=p.date,
            pnl_pct=(p.total_unrealized_pnl_amount / p.total_cost_sgd * 100) if p.total_cost_sgd else 0.0,
        )
        for p in get_portfolio_value_series(as_of)
    ]


def get_overlay_series(as_of: date) -> dict[str, list[OverlayPoint]]:
    """Unrealized PnL % over time per currently-active holding — (value -
    cost) / cost using the actual cost basis, the same figure 'View Stocks'
    shows for as_of alone, just as a full history. Deliberately NOT price
    movement since date_added: your cost basis is whatever you told the
    tracker you paid, which can differ from that day's market price, so a
    pure-price comparison could show 0% (or the wrong sign) even while
    you're genuinely up or down relative to what you actually paid."""
    user = get_default_user()
    start = _range_start(as_of)
    holdings = list(Holding.select().where(Holding.user == user, Holding.is_active == True))  # noqa: E712

    result: dict[str, list[OverlayPoint]] = {}
    for holding in holdings:
        # See get_stock_graph_series for the two cases. Fall back only when the holding
        # existed by as_of but no trading day has happened since (weekend purchase);
        # a holding added after as_of is omitted from the response entirely rather than
        # drawn at a fabricated 0%.
        clamp_start = max(start, holding.date_added)
        axis = _build_axis([holding.ticker], clamp_start, as_of)
        if not axis:
            if clamp_start > as_of:
                continue
            axis = [as_of]

        points = _holding_daily_series(holding, axis, as_of)
        result[holding.ticker] = [
            OverlayPoint(date=p.date, pnl_pct=(p.unrealized_pnl / p.cost_sgd * 100) if p.cost_sgd else 0.0)
            for p in points
        ]

    return result
