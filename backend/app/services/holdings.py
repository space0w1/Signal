from datetime import date

from peewee import fn

from app.models import Holding, Purchase, PriceHistory, User
from app.services.market_data import backfill_price_history, currency_for_region

DEFAULT_USER_ID = 1


class RegionMismatchError(Exception):
    pass


def get_default_user() -> User:
    """Single-user app today (README: 'Zero-Authentication Model') — everything
    is still keyed by user_id so real multi-user support later is additive."""
    user, _ = User.get_or_create(id=DEFAULT_USER_ID)
    return user


def _recompute_totals(holding: Holding) -> None:
    """Refreshes the total_quantity/total_cost cache from `purchases` —
    the source of truth — bounded to the holding's current active window
    (purchases from an earlier stint, before a soft-delete, are excluded)."""
    agg = (
        Purchase.select(
            fn.SUM(Purchase.quantity).alias("qty"),
            fn.SUM(Purchase.quantity * Purchase.price).alias("cost"),
        )
        .where(Purchase.holding == holding, Purchase.purchase_date >= holding.date_added)
        .dicts()
        .get()
    )
    holding.total_quantity = agg["qty"] or 0
    holding.total_cost = agg["cost"] or 0
    holding.save()


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
        # window — purchases from the earlier stint stay in the table but
        # are excluded from the cache/point-in-time queries by date_added.
        holding.date_added = today
        holding.is_active = True
        holding.removed_date = None
        holding.save()

    Purchase.create(holding=holding, quantity=qty, price=cost, purchase_date=today)
    _recompute_totals(holding)

    return holding
