from datetime import date, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.services.news import get_news_for_date, refresh_news

router = APIRouter(tags=["news"])


class NewsItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    headline: str
    source: str | None
    url: str | None
    thumbnail_url: str | None
    published_at: datetime | None
    fetched_date: date


class NewsRefreshResponse(BaseModel):
    ticker: str
    rows_inserted: int


@router.get("/news/stock/{ticker}", response_model=list[NewsItemResponse])
def news_for_stock(
    ticker: str,
    as_of: date | None = Query(default=None, alias="date"),
) -> list[NewsItemResponse]:
    as_of = as_of or date.today()
    items = get_news_for_date(ticker.upper(), as_of)
    return [NewsItemResponse.model_validate(item) for item in items]


@router.post("/news/{ticker}/refresh", response_model=NewsRefreshResponse)
def trigger_news_refresh(ticker: str) -> NewsRefreshResponse:
    ticker = ticker.upper()
    rows_inserted = refresh_news(ticker)
    return NewsRefreshResponse(ticker=ticker, rows_inserted=rows_inserted)
