from dataclasses import dataclass
from datetime import date

from app.models import FxRate, Holding, PriceHistory
from app.services.holdings import get_default_user


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
    pnl_amount: float
    pnl_pct: float


@dataclass
class PortfolioValuation:
    date: date
    total_value_sgd: float
    total_cost_sgd: float
    pnl_amount: float
    pnl_pct: float
    holdings: list[HoldingValuation]


def get_portfolio(as_of: date | None = None) -> PortfolioValuation:
    """Values the portfolio as of as_of (default today) using whatever price
    and FX data was actually true on that date — not today's. Cost basis is
    assumed constant across a holding's whole active window (see
    docs/database.md), and is converted to SGD using the same as-of FX rate
    as the current value, since the app doesn't track the FX rate at the
    time of each individual purchase.
    """
    as_of = as_of or date.today()
    user = get_default_user()

    active_holdings = Holding.select().where(
        Holding.user == user,
        Holding.date_added <= as_of,
        Holding.removed_date.is_null(True) | (Holding.removed_date > as_of),
    )

    valuations: list[HoldingValuation] = []
    for holding in active_holdings:
        price_row = _latest_price(holding.ticker, as_of)
        if price_row is None:
            continue  # no price data available on/before this date yet

        fx_rate = _latest_fx_rate(holding.currency, as_of)
        if fx_rate is None:
            continue  # no fx data available on/before this date yet

        value_sgd = holding.total_quantity * price_row.close_price * fx_rate
        cost_sgd = holding.total_cost * fx_rate
        pnl_amount = value_sgd - cost_sgd
        pnl_pct = (pnl_amount / cost_sgd * 100) if cost_sgd else 0.0

        valuations.append(
            HoldingValuation(
                ticker=holding.ticker,
                exchange=holding.exchange,
                currency=holding.currency,
                quantity=holding.total_quantity,
                price=price_row.close_price,
                price_date=price_row.date,
                value_sgd=value_sgd,
                cost_sgd=cost_sgd,
                pnl_amount=pnl_amount,
                pnl_pct=pnl_pct,
            )
        )

    valuations.sort(key=lambda v: v.pnl_amount, reverse=True)

    total_value_sgd = sum(v.value_sgd for v in valuations)
    total_cost_sgd = sum(v.cost_sgd for v in valuations)
    total_pnl = total_value_sgd - total_cost_sgd
    total_pnl_pct = (total_pnl / total_cost_sgd * 100) if total_cost_sgd else 0.0

    return PortfolioValuation(
        date=as_of,
        total_value_sgd=total_value_sgd,
        total_cost_sgd=total_cost_sgd,
        pnl_amount=total_pnl,
        pnl_pct=total_pnl_pct,
        holdings=valuations,
    )
