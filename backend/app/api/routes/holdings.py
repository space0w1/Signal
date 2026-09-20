from datetime import date as Date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.holdings import (
    HoldingNotFoundError,
    InsufficientQuantityError,
    InvalidTransactionDateError,
    RegionMismatchError,
    add_holding,
    sell_holding,
)
from app.services.market_data import (
    UnknownTickerError,
    UnsupportedMarketError,
    backfill_price_history,
    refresh_price_history,
)

router = APIRouter(tags=["holdings"])

class AddHoldingRequest(BaseModel):
    # No `region` field: it is resolved from the currency Yahoo reports for the symbol
    # (see services/market_data.region_for_currency). Accepting it let a caller pair a
    # Vienna listing with region='US', storing euro prices as USD — wrong valuations
    # with nothing failing. The response still reports the region that was resolved.
    symbol: str
    qty: float = Field(gt=0)
    cost: float = Field(gt=0)
    date: Date | None = None  # purchase date; defaults to today if omitted


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    exchange: str
    currency: str
    total_quantity: float
    total_cost: float
    realized_pnl: float
    date_added: Date
    is_active: bool


class SellHoldingRequest(BaseModel):
    qty: float = Field(gt=0)
    price: float = Field(gt=0)
    date: Date | None = None  # sale date; defaults to today if omitted


class SellHoldingResponse(BaseModel):
    id: int
    ticker: str
    exchange: str
    currency: str
    total_quantity: float
    total_cost: float
    realized_pnl: float
    is_active: bool
    removed_date: Date | None
    sale_realized_pnl: float


class BackfillResponse(BaseModel):
    ticker: str
    rows_inserted: int


@router.post("/holdings", response_model=HoldingResponse)
def create_holding(payload: AddHoldingRequest) -> HoldingResponse:
    ticker = payload.symbol.upper()
    try:
        holding = add_holding(ticker, payload.qty, payload.cost, payload.date)
    except (
        UnknownTickerError,
        UnsupportedMarketError,
        RegionMismatchError,
        InvalidTransactionDateError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HoldingResponse.model_validate(holding)


@router.post("/holdings/{ticker}/sell", response_model=SellHoldingResponse)
def sell(ticker: str, payload: SellHoldingRequest) -> SellHoldingResponse:
    ticker = ticker.upper()
    try:
        result = sell_holding(ticker, payload.qty, payload.price, payload.date)
    except HoldingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InsufficientQuantityError, InvalidTransactionDateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    holding = result.holding
    return SellHoldingResponse(
        id=holding.id,
        ticker=holding.ticker,
        exchange=holding.exchange,
        currency=holding.currency,
        total_quantity=holding.total_quantity,
        total_cost=holding.total_cost,
        realized_pnl=holding.realized_pnl,
        is_active=holding.is_active,
        removed_date=holding.removed_date,
        sale_realized_pnl=result.realized_pnl,
    )


@router.post("/price-history/{ticker}/backfill", response_model=BackfillResponse)
def trigger_backfill(ticker: str) -> BackfillResponse:
    """Region is no longer a query param — the backfill derives it from the currency
    Yahoo reports, the same way POST /holdings does."""
    ticker = ticker.upper()
    try:
        rows_inserted, _region, _currency = backfill_price_history(ticker)
    except UnknownTickerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnsupportedMarketError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BackfillResponse(ticker=ticker, rows_inserted=rows_inserted)


@router.post("/price-history/{ticker}/refresh", response_model=BackfillResponse)
def trigger_price_refresh(ticker: str) -> BackfillResponse:
    ticker = ticker.upper()
    try:
        rows_inserted = refresh_price_history(ticker)
    except UnknownTickerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BackfillResponse(ticker=ticker, rows_inserted=rows_inserted)
