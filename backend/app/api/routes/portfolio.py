from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.services.portfolio import get_portfolio

router = APIRouter(tags=["portfolio"])


class HoldingPnLResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    total_value_sgd: float
    total_cost_sgd: float
    total_unrealized_pnl_amount: float
    total_unrealized_pnl_pct: float
    total_realized_pnl_sgd: float
    holdings: list[HoldingPnLResponse]


@router.get("/portfolio", response_model=PortfolioResponse)
def read_portfolio(as_of: date | None = Query(default=None, alias="date")) -> PortfolioResponse:
    return PortfolioResponse.model_validate(get_portfolio(as_of))
