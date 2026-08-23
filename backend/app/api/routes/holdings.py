from datetime import date as Date
from typing import Literal

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
from app.services.market_data import UnknownTickerError, backfill_price_history, currency_for_region

router = APIRouter(tags=["holdings"])

Region = Literal["US", "HK", "SG"]


class AddHoldingRequest(BaseModel):
    symbol: str
    region: Region
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
        holding = add_holding(ticker, payload.qty, payload.cost, payload.region, payload.date)
    except (UnknownTickerError, RegionMismatchError, InvalidTransactionDateError) as exc:
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
def trigger_backfill(ticker: str, region: Region) -> BackfillResponse:
    ticker = ticker.upper()
    currency = currency_for_region(region)
    try:
        rows_inserted = backfill_price_history(ticker, currency)
    except UnknownTickerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BackfillResponse(ticker=ticker, rows_inserted=rows_inserted)
