from dataclasses import dataclass
from datetime import date

from app.models import FxRate, Holding, PriceHistory
from app.services.holdings import get_default_user
from app.services.transactions import replay_transactions


def _latest_price(ticker: str, as_of: date) -> PriceHistory | None:
    """Most recent close on or before as_of — handles weekends/holidays where
    the requested date itself has no trading data."""
    return (
        PriceHistory.select()
        .where(PriceHistory.ticker == ticker, PriceHistory.date <= as_of)
        .order_by(PriceHistory.date.desc())
        .first()
    )


def _latest_fx_rate(currency: str, as_of: date) -> float | None:
    if currency == "SGD":
        return 1.0
    pair = f"{currency}SGD"
    row = (
        FxRate.select()
        .where(FxRate.currency_pair == pair, FxRate.date <= as_of)
        .order_by(FxRate.date.desc())
        .first()
    )
    return row.rate if row else None


@dataclass
class HoldingValuation:
    ticker: str
    exchange: str
    currency: str
    quantity: float
    price: float
    price_date: date
    value_sgd: float
    cost_sgd: float
    unrealized_pnl_amount: float
    unrealized_pnl_pct: float
    realized_pnl_sgd: float


@dataclass
class PortfolioValuation:
    date: date
    total_value_sgd: float
    total_cost_sgd: float
    total_unrealized_pnl_amount: float
    total_unrealized_pnl_pct: float
    total_realized_pnl_sgd: float
    holdings: list[HoldingValuation]


def get_portfolio(as_of: date | None = None) -> PortfolioValuation:
    """Values the portfolio as of as_of (default today) using whatever price
    and FX data was actually true on that date — not today's. Quantity, cost
    basis, and realized PnL are all reconstructed by replaying transactions
    up to as_of (see services/transactions.py), not read from the holding's
    current cache, so a past snapshot reflects only what had happened by
    then. Realized PnL is converted to SGD using the same as-of FX rate as
    everything else, since the app doesn't track the FX rate at the time of
    each individual transaction.
    """
    as_of = as_of or date.today()
    user = get_default_user()

    active_holdings = Holding.select().where(
        Holding.user == user,
        Holding.date_added <= as_of,
        # >= not >: the removal day itself should still show the position
        # (typically at zero quantity), since that's the day its closing
        # sale's realized PnL happened — excluding it would hide that gain.
        Holding.removed_date.is_null(True) | (Holding.removed_date >= as_of),
    )

    valuations: list[HoldingValuation] = []
    for holding in active_holdings:
        price_row = _latest_price(holding.ticker, as_of)
        if price_row is None:
            continue  # no price data available on/before this date yet

        fx_rate = _latest_fx_rate(holding.currency, as_of)
        if fx_rate is None:
            continue  # no fx data available on/before this date yet

        replay = replay_transactions(holding, as_of)
        if replay.quantity == 0 and replay.realized_pnl == 0:
            continue  # nothing owned and nothing sold as of this date

        value_sgd = replay.quantity * price_row.close_price * fx_rate
        cost_sgd = replay.cost_basis * fx_rate
        unrealized_pnl_amount = value_sgd - cost_sgd
        unrealized_pnl_pct = (unrealized_pnl_amount / cost_sgd * 100) if cost_sgd else 0.0
        realized_pnl_sgd = replay.realized_pnl * fx_rate

        valuations.append(
            HoldingValuation(
                ticker=holding.ticker,
                exchange=holding.exchange,
                currency=holding.currency,
                quantity=replay.quantity,
                price=price_row.close_price,
                price_date=price_row.date,
                value_sgd=value_sgd,
                cost_sgd=cost_sgd,
                unrealized_pnl_amount=unrealized_pnl_amount,
                unrealized_pnl_pct=unrealized_pnl_pct,
                realized_pnl_sgd=realized_pnl_sgd,
            )
        )

    valuations.sort(key=lambda v: v.unrealized_pnl_amount + v.realized_pnl_sgd, reverse=True)

    total_value_sgd = sum(v.value_sgd for v in valuations)
    total_cost_sgd = sum(v.cost_sgd for v in valuations)
    total_unrealized = total_value_sgd - total_cost_sgd
    total_unrealized_pct = (total_unrealized / total_cost_sgd * 100) if total_cost_sgd else 0.0
    total_realized_sgd = sum(v.realized_pnl_sgd for v in valuations)

    return PortfolioValuation(
        date=as_of,
        total_value_sgd=total_value_sgd,
        total_cost_sgd=total_cost_sgd,
        total_unrealized_pnl_amount=total_unrealized,
        total_unrealized_pnl_pct=total_unrealized_pct,
        total_realized_pnl_sgd=total_realized_sgd,
        holdings=valuations,
    )
