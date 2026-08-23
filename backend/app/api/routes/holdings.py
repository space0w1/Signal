from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.holdings import RegionMismatchError, add_holding
from app.services.market_data import UnknownTickerError, backfill_price_history, currency_for_region

router = APIRouter(tags=["holdings"])

Region = Literal["US", "HK", "SG"]


class AddHoldingRequest(BaseModel):
    symbol: str
    region: Region
    qty: float = Field(gt=0)
    cost: float = Field(gt=0)


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    exchange: str
    currency: str
    total_quantity: float
    total_cost: float
    date_added: date
    is_active: bool


class BackfillResponse(BaseModel):
    ticker: str
    rows_inserted: int


@router.post("/holdings", response_model=HoldingResponse)
def create_holding(payload: AddHoldingRequest) -> HoldingResponse:
    ticker = payload.symbol.upper()
    try:
        holding = add_holding(ticker, payload.qty, payload.cost, payload.region)
    except (UnknownTickerError, RegionMismatchError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HoldingResponse.model_validate(holding)


@router.post("/price-history/{ticker}/backfill", response_model=BackfillResponse)
def trigger_backfill(ticker: str, region: Region) -> BackfillResponse:
    ticker = ticker.upper()
    currency = currency_for_region(region)
    try:
        rows_inserted = backfill_price_history(ticker, currency)
    except UnknownTickerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BackfillResponse(ticker=ticker, rows_inserted=rows_inserted)
