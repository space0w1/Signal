from datetime import date

from app.models import Holding, PriceHistory, User
from app.services.market_data import backfill_price_history, currency_for_region

DEFAULT_USER_ID = 1


class RegionMismatchError(Exception):
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

    holding = Holding.get_or_none(Holding.user == user, Holding.ticker == ticker)

    if holding is not None and holding.exchange != region:
        raise RegionMismatchError(
            f"'{ticker}' is already tracked as region '{holding.exchange}', got '{region}'"
        )

    if holding is not None and holding.is_active:
        holding.total_quantity += qty
        holding.total_cost += qty * cost
        holding.save()
    elif holding is not None:
        # Ticker was previously soft-deleted. Treat this as a fresh position
        # rather than resuming the old cost basis.
        holding.total_quantity = qty
        holding.total_cost = qty * cost
        holding.date_added = date.today()
        holding.is_active = True
        holding.removed_date = None
        holding.save()
    else:
        holding = Holding.create(
            user=user,
            ticker=ticker,
            exchange=region,
            currency=currency,
            total_quantity=qty,
            total_cost=qty * cost,
            date_added=date.today(),
            is_active=True,
        )

    return holding
