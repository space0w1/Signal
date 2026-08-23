from dataclasses import dataclass
from datetime import date

from app.models import Holding, PriceHistory, Transaction, User
from app.services.market_data import backfill_price_history, currency_for_region
from app.services.transactions import refresh_holding_cache

DEFAULT_USER_ID = 1


class RegionMismatchError(Exception):
    pass


class HoldingNotFoundError(Exception):
    pass


class InsufficientQuantityError(Exception):
    pass


def get_default_user() -> User:
    """Single-user app today (README: 'Zero-Authentication Model') — everything
    is still keyed by user_id so real multi-user support later is additive."""
    user, _ = User.get_or_create(id=DEFAULT_USER_ID)
    return user


def add_holding(ticker: str, qty: float, cost: float, region: str) -> Holding:
    user = get_default_user()
    currency = currency_for_region(region)
    is_new_ticker = not PriceHistory.select().where(PriceHistory.ticker == ticker).exists()

    # Backfill before touching the holdings table: if the ticker is invalid,
    # fail loudly here rather than leaving behind a holding with no price data.
    if is_new_ticker:
        backfill_price_history(ticker, currency)

    today = date.today()
    holding = Holding.get_or_none(Holding.user == user, Holding.ticker == ticker)

    if holding is not None and holding.exchange != region:
        raise RegionMismatchError(
            f"'{ticker}' is already tracked as region '{holding.exchange}', got '{region}'"
        )

    if holding is None:
        holding = Holding.create(
            user=user,
            ticker=ticker,
            exchange=region,
            currency=currency,
            total_quantity=0,
            total_cost=0,
            date_added=today,
            is_active=True,
        )
    elif not holding.is_active:
        # Reactivating a previously soft-deleted position starts a fresh
        # window — transactions from the earlier stint stay in the table but
        # are excluded from the cache/point-in-time queries by date_added.
        holding.date_added = today
        holding.is_active = True
        holding.removed_date = None
        holding.save()

    Transaction.create(holding=holding, type="buy", quantity=qty, price=cost, transaction_date=today)
    refresh_holding_cache(holding)

    return holding


@dataclass
class SaleResult:
    holding: Holding
    realized_pnl: float  # native currency, gain/loss from this sale only


def sell_holding(ticker: str, qty: float, price: float) -> SaleResult:
    user = get_default_user()
    holding = Holding.get_or_none(Holding.user == user, Holding.ticker == ticker, Holding.is_active == True)  # noqa: E712
    if holding is None:
        raise HoldingNotFoundError(f"No active holding for '{ticker}'")

    if qty > holding.total_quantity + 1e-9:
        raise InsufficientQuantityError(
            f"Cannot sell {qty} shares of '{ticker}', only {holding.total_quantity} held"
        )

    avg_cost = (holding.total_cost / holding.total_quantity) if holding.total_quantity else 0.0
    sale_realized_pnl = qty * (price - avg_cost)

    today = date.today()
    Transaction.create(holding=holding, type="sell", quantity=qty, price=price, transaction_date=today)
    refresh_holding_cache(holding)

    if holding.total_quantity <= 1e-9:
        holding.is_active = False
        holding.removed_date = today
        holding.save()

    return SaleResult(holding=holding, realized_pnl=sale_realized_pnl)
