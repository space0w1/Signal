import json
from datetime import date, datetime

from pydantic import BaseModel

from app.models import NewsItem, Summary
from app.services.holdings import get_default_user
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.news import get_news_for_date
from app.services.portfolio import get_portfolio
from app.services.prompts import PORTFOLIO_SUMMARY_PROMPT, STOCK_SUMMARY_PROMPT

PORTFOLIO_SENTINEL = "__portfolio__"
ARTICLE_TEXT_CHARS = 2000  # per-article context cap, keeps the prompt bounded


class SummaryGenerationError(Exception):
    pass


class PortfolioSummaryOutput(BaseModel):
    summary: str
    next_steps: str
    cited_news_ids: list[int]


class StockSummaryOutput(BaseModel):
    summary: str
    next_steps: str


def _news_context(news_items: list[NewsItem]) -> str:
    if not news_items:
        return "(no recent news available)"
    parts = []
    for item in news_items:
        body = (item.article_text or item.headline)[:ARTICLE_TEXT_CHARS]
        parts.append(f"[news_id={item.id}] {item.headline} ({item.source})\n{body}")
    return "\n\n".join(parts)


def _generate(prompt: str, output_schema: type[BaseModel]) -> BaseModel:
    try:
        return get_llm_provider().generate(prompt, output_schema)
    except LLMProviderError as exc:
        raise SummaryGenerationError(str(exc)) from exc


def _generate_portfolio_summary(as_of: date) -> tuple[str, str, list[int]]:
    portfolio = get_portfolio(as_of)

    news_items: list[NewsItem] = []
    for holding in portfolio.holdings:
        news_items.extend(get_news_for_date(holding.ticker, as_of))

    holdings_lines = "\n".join(
        f"- {h.ticker}: {h.quantity} sh, value S${h.value_sgd:.2f}, "
        f"unrealized PnL S${h.unrealized_pnl_amount:.2f} ({h.unrealized_pnl_pct:.1f}%)"
        for h in portfolio.holdings
    )

    prompt = PORTFOLIO_SUMMARY_PROMPT.format(
        as_of=as_of,
        total_value=portfolio.total_value_sgd,
        unrealized_pnl=portfolio.total_unrealized_pnl_amount,
        unrealized_pnl_pct=portfolio.total_unrealized_pnl_pct,
        realized_pnl=portfolio.total_realized_pnl_sgd,
        holdings_lines=holdings_lines or "(no holdings)",
        news_context=_news_context(news_items),
    )

    result = _generate(prompt, PortfolioSummaryOutput)
    assert isinstance(result, PortfolioSummaryOutput)
    return result.summary, result.next_steps, result.cited_news_ids


def _generate_stock_summary(ticker: str, as_of: date) -> tuple[str, str]:
    portfolio = get_portfolio(as_of)
    holding = next((h for h in portfolio.holdings if h.ticker == ticker), None)
    news_items = get_news_for_date(ticker, as_of)

    if holding is not None:
        position_line = (
            f"{holding.quantity} sh @ avg {holding.avg_cost:.2f} {holding.currency}, "
            f"current price {holding.price:.2f} {holding.currency}, "
            f"unrealized PnL S${holding.unrealized_pnl_amount:.2f} ({holding.unrealized_pnl_pct:.1f}%)"
        )
    else:
        position_line = "(not currently held)"

    prompt = STOCK_SUMMARY_PROMPT.format(
        ticker=ticker,
        as_of=as_of,
        position_line=position_line,
        news_context=_news_context(news_items),
    )

    result = _generate(prompt, StockSummaryOutput)
    assert isinstance(result, StockSummaryOutput)
    return result.summary, result.next_steps


def get_or_generate_summary(target_type: str, ticker: str, as_of: date) -> Summary:
    """target_type is 'portfolio' or 'stock'; ticker is ignored for
    'portfolio' (the sentinel is used instead). Checks the `summaries`
    cache first; generates + persists on a miss (docs/api.md: on-demand
    fallback) — the same pattern nightly cron will later pre-warm."""
    user = get_default_user()
    cache_key_ticker = PORTFOLIO_SENTINEL if target_type == "portfolio" else ticker

    cached = Summary.get_or_none(
        Summary.user == user,
        Summary.target_type == target_type,
        Summary.ticker == cache_key_ticker,
        Summary.date == as_of,
    )
    if cached is not None:
        return cached

    if target_type == "portfolio":
        summary_text, next_steps_text, cited_ids = _generate_portfolio_summary(as_of)
        cited_json = json.dumps(cited_ids)
    else:
        summary_text, next_steps_text = _generate_stock_summary(ticker, as_of)
        cited_json = None

    return Summary.create(
        user=user,
        target_type=target_type,
        ticker=cache_key_ticker,
        date=as_of,
        summary_text=summary_text,
        next_steps_text=next_steps_text,
        cited_news_ids=cited_json,
        generated_at=datetime.utcnow(),
    )
