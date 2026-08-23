from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.services.graph import get_overlay_series, get_portfolio_value_series, get_stock_price_series

router = APIRouter(tags=["graph"])

Mode = Literal["aggregate", "overlay"]


class AggregatePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    total_value_sgd: float
    total_cost_sgd: float
    total_unrealized_pnl_amount: float
    total_realized_pnl_sgd: float


class OverlayPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    return_pct: float


class GraphResponse(BaseModel):
    mode: Mode
    aggregate: list[AggregatePointResponse] | None = None
    overlay: dict[str, list[OverlayPointResponse]] | None = None


class StockPricePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    price: float
    currency: str


@router.get("/graph/portfolio", response_model=GraphResponse)
def graph_portfolio(
    as_of: date | None = Query(default=None, alias="date"),
    mode: Mode = "aggregate",
) -> GraphResponse:
    as_of = as_of or date.today()
    if mode == "aggregate":
        points = [AggregatePointResponse.model_validate(p) for p in get_portfolio_value_series(as_of)]
        return GraphResponse(mode=mode, aggregate=points)

    overlay = {
        ticker: [OverlayPointResponse.model_validate(p) for p in points]
        for ticker, points in get_overlay_series(as_of).items()
    }
    return GraphResponse(mode=mode, overlay=overlay)


@router.get("/graph/stock/{ticker}", response_model=list[StockPricePointResponse])
def graph_stock(
    ticker: str,
    as_of: date | None = Query(default=None, alias="date"),
) -> list[StockPricePointResponse]:
    as_of = as_of or date.today()
    points = get_stock_price_series(ticker.upper(), as_of)
    return [StockPricePointResponse.model_validate(p) for p in points]
