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
    return_pct: float


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


def get_overlay_series(as_of: date) -> dict[str, list[OverlayPoint]]:
    """Normalized % price return per currently-active holding, each series
    starting at 0% on the later of (holding's date_added, 5yr ago) — pure
    price movement, no FX/quantity/cost involved, since this compares
    relative stock performance rather than portfolio value contribution."""
    user = get_default_user()
    start = _range_start(as_of)
    holdings = Holding.select().where(Holding.user == user, Holding.is_active == True)  # noqa: E712

    result: dict[str, list[OverlayPoint]] = {}
    for holding in holdings:
        range_start = max(start, holding.date_added)
        prices = list(
            PriceHistory.select()
            .where(
                PriceHistory.ticker == holding.ticker,
                PriceHistory.date >= range_start,
                PriceHistory.date <= as_of,
            )
            .order_by(PriceHistory.date)
        )
        if not prices:
            continue

        base_price = prices[0].close_price
        result[holding.ticker] = [
            OverlayPoint(date=p.date, return_pct=((p.close_price / base_price) - 1) * 100) for p in prices
        ]

    return result
