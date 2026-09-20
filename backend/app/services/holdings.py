from contextlib import suppress
from dataclasses import dataclass
from datetime import date

from app.models import Holding, NewsItem, PriceHistory, Transaction, User
from app.services.market_data import (
    CURRENCY_REGION,
    UnsupportedMarketError,
    backfill_price_history,
)
from app.services.news import refresh_news
from app.services.transactions import refresh_holding_cache, replay_transactions

DEFAULT_USER_ID = 1


class RegionMismatchError(Exception):
    pass


class HoldingNotFoundError(Exception):
    pass


class InsufficientQuantityError(Exception):
    pass


class InvalidTransactionDateError(Exception):
    pass


def get_default_user() -> User:
    """Single-user app today (README: 'Zero-Authentication Model') — everything
    is still keyed by user_id so real multi-user support later is additive."""
    user, _ = User.get_or_create(id=DEFAULT_USER_ID)
    return user


def list_tracked_tickers() -> list[str]:
    """Tickers with a currently-active holding — what the nightly job refreshes.
    Closed-out positions are deliberately excluded: their quantity is zero from
    the closing sale onward, so a fresh price would change nothing on any chart
    or valuation. Their historical rows still matter and are never touched."""
    user = get_default_user()
    rows = (
        Holding.select(Holding.ticker)
        .where(Holding.user == user, Holding.is_active == True)  # noqa: E712
        .distinct()
        .order_by(Holding.ticker)
    )
    return [row.ticker for row in rows]


def add_holding(
    ticker: str,
    qty: float,
    cost: float,
    purchase_date: date | None = None,
) -> Holding:
    """Region is deliberately NOT a parameter: it is derived from the currency Yahoo
    reports for the ticker (see market_data.region_for_currency). A caller-supplied
    region could be wrong in a way nothing detects — a Vienna listing declared 'US'
    stores euro prices as USD and converts them at the USD rate."""
    today = date.today()
    purchase_date = purchase_date or today
    if purchase_date > today:
        raise InvalidTransactionDateError(f"Purchase date {purchase_date} is in the future")

    user = get_default_user()
    existing_price = PriceHistory.select().where(PriceHistory.ticker == ticker).first()

    # Backfill before touching the holdings table: if the ticker is invalid, fail loudly
    # here rather than leaving behind a holding with no price data. The backfill is also
    # what tells us the region, so for an untracked ticker it has to run first; for one
    # already tracked, the stored rows already carry the currency it was resolved to.
    if existing_price is None:
        _, region, currency = backfill_price_history(ticker)
    else:
        currency = existing_price.currency
        region = CURRENCY_REGION.get(currency)
        if region is None:
            raise UnsupportedMarketError(
                f"'{ticker}' has stored prices in {currency}, which is no longer supported"
            )

    # Seed today's news if we have none for this ticker yet. Covers a brand-new
    # ticker and one being re-added after being sold out (the nightly job only
    # refreshes active holdings, so an inactive ticker's news went stale). Without
    # this, the ticker's first summary has nothing to work with, isn't cached
    # (see get_or_generate_summary), and re-bills an LLM call on every view until
    # the nightly run. Best-effort, unlike the price backfill above: yfinance
    # returning no news for a perfectly valid ticker is normal and is no reason to
    # reject the holding. Naturally idempotent — adding twice in a day fetches once.
    if not NewsItem.select().where(
        NewsItem.ticker == ticker, NewsItem.fetched_date == today
    ).exists():
        with suppress(Exception):
            refresh_news(ticker)

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
            date_added=purchase_date,
            is_active=True,
        )
    elif not holding.is_active:
        # Reactivating a previously soft-deleted position starts a fresh
        # window — transactions from the earlier stint stay in the table but
        # are excluded from the cache/point-in-time queries by date_added.
        holding.date_added = purchase_date
        holding.is_active = True
        holding.removed_date = None
        holding.save()
    elif purchase_date < holding.date_added:
        raise InvalidTransactionDateError(
            f"Purchase date {purchase_date} is before '{ticker}' was first tracked ({holding.date_added})"
        )

    Transaction.create(holding=holding, type="buy", quantity=qty, price=cost, transaction_date=purchase_date)
    refresh_holding_cache(holding)

    return holding


@dataclass
class SaleResult:
    holding: Holding
    realized_pnl: float  # native currency, gain/loss from this sale only


def sell_holding(ticker: str, qty: float, price: float, sale_date: date | None = None) -> SaleResult:
    user = get_default_user()
    holding = Holding.get_or_none(Holding.user == user, Holding.ticker == ticker, Holding.is_active == True)  # noqa: E712
    if holding is None:
        raise HoldingNotFoundError(f"No active holding for '{ticker}'")

    today = date.today()
    sale_date = sale_date or today
    if sale_date > today:
        raise InvalidTransactionDateError(f"Sale date {sale_date} is in the future")
    if sale_date < holding.date_added:
        raise InvalidTransactionDateError(
            f"Sale date {sale_date} is before '{ticker}' was first tracked ({holding.date_added})"
        )

    # State as of sale_date, not today's cache — sale_date may be backdated
    # to before later transactions, so the average cost at the time of this
    # sale (and how much was actually held then) can differ from today's.
    state_before_sale = replay_transactions(holding, sale_date)
    if qty > state_before_sale.quantity + 1e-9:
        raise InsufficientQuantityError(
            f"Cannot sell {qty} shares of '{ticker}' as of {sale_date}, only "
            f"{state_before_sale.quantity} were held then"
        )

    avg_cost = (state_before_sale.cost_basis / state_before_sale.quantity) if state_before_sale.quantity else 0.0
    sale_realized_pnl = qty * (price - avg_cost)

    Transaction.create(holding=holding, type="sell", quantity=qty, price=price, transaction_date=sale_date)
    refresh_holding_cache(holding)

    if holding.total_quantity <= 1e-9:
        holding.is_active = False
        holding.removed_date = sale_date
        holding.save()

    return SaleResult(holding=holding, realized_pnl=sale_realized_pnl)
