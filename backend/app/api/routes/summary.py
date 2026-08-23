import json
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.routes.news import NewsItemResponse
from app.models import NewsItem
from app.services.summaries import SummaryGenerationError, get_or_generate_summary

router = APIRouter(tags=["summary"])


class SummaryResponse(BaseModel):
    target_type: str
    ticker: str | None
    date: date
    summary: str
    next_steps: str
    cited_news: list[NewsItemResponse]
    generated_at: str


@router.get("/summary", response_model=SummaryResponse)
def read_summary(
    target: str = Query(..., description="'portfolio' or a ticker symbol"),
    as_of: date | None = Query(default=None, alias="date"),
) -> SummaryResponse:
    as_of = as_of or date.today()
    target_type = "portfolio" if target.lower() == "portfolio" else "stock"
    ticker = target.upper() if target_type == "stock" else ""

    try:
        summary = get_or_generate_summary(target_type, ticker, as_of)
    except SummaryGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    cited_ids: list[int] = json.loads(summary.cited_news_ids) if summary.cited_news_ids else []
    cited_news: list[NewsItemResponse] = []
    if cited_ids:
        items_by_id = {item.id: item for item in NewsItem.select().where(NewsItem.id.in_(cited_ids))}
        cited_news = [
            NewsItemResponse.model_validate(items_by_id[news_id])
            for news_id in cited_ids
            if news_id in items_by_id
        ]

    return SummaryResponse(
        target_type=summary.target_type,
        ticker=None if summary.target_type == "portfolio" else summary.ticker,
        date=summary.date,
        summary=summary.summary_text,
        next_steps=summary.next_steps_text or "",
        cited_news=cited_news,
        generated_at=summary.generated_at.isoformat(),
    )
