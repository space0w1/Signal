from datetime import date, datetime

import trafilatura
import yfinance as yf

from app.db import database
from app.models import NewsItem

FETCH_LIMIT = 5  # matches what the AI summary will use as citation candidates


def _parse_published_at(item: dict) -> datetime | None:
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    raw = content.get("pubDate") or content.get("displayTime") or item.get("providerPublishTime")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw)
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_thumbnail(content: dict) -> str | None:
    thumbnail = content.get("thumbnail") or {}
    resolutions = thumbnail.get("resolutions") or []
    if resolutions:
        smallest = min(resolutions, key=lambda r: r.get("width") or float("inf"))
        if smallest.get("url"):
            return smallest["url"]
    return thumbnail.get("originalUrl")


def _fetch_article_text(url: str) -> str | None:
    """Downloads and extracts clean article text via trafilatura (see
    backend/tests/test_yahoo.py). Best-effort: many sites block scrapers or
    paywall content, so a failure here shouldn't fail the whole refresh."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        return trafilatura.extract(downloaded)
    except Exception:
        return None


def fetch_news(ticker: str) -> list[dict]:
    """The FETCH_LIMIT most recent news items for a ticker via yfinance,
    normalized across its old/new schema variants (see
    backend/tests/test_yahoo.py, which prototyped this same normalization
    for article-text extraction)."""
    stock = yf.Ticker(ticker)
    raw_items = (stock.news or [])[:FETCH_LIMIT]

    normalized = []
    for item in raw_items:
        content = item.get("content") if isinstance(item.get("content"), dict) else item

        title = content.get("title") or item.get("title") or "No Title"
        publisher = (content.get("provider") or {}).get("displayName") or item.get("publisher")

        click_through = content.get("canonicalUrl") or content.get("clickThroughUrl")
        url = (
            click_through.get("url")
            if isinstance(click_through, dict)
            else content.get("link") or item.get("link")
        )

        normalized.append(
            {
                "headline": title,
                "source": publisher,
                "url": url,
                "thumbnail_url": _extract_thumbnail(content),
                "article_text": _fetch_article_text(url) if url else None,
                "published_at": _parse_published_at(item),
            }
        )

    return normalized


def refresh_news(ticker: str) -> int:
    """Fetches today's news for a ticker and records it under today's
    fetched_date. An article already seen on a previous fetch still gets
    a fresh row for today (see NewsItem docstring) — a past-date query
    should show exactly what yfinance returned that day."""
    items = fetch_news(ticker)
    today = date.today()

    rows = [
        {
            "ticker": ticker,
            "headline": item["headline"],
            "source": item["source"],
            "url": item["url"],
            "thumbnail_url": item["thumbnail_url"],
            "article_text": item["article_text"],
            "published_at": item["published_at"],
            "fetched_date": today,
        }
        for item in items
        if item["url"]
    ]
    if not rows:
        return 0

    with database.atomic():
        NewsItem.insert_many(rows).on_conflict_ignore().execute()

    return len(rows)


def get_news_for_date(ticker: str, fetched_date: date) -> list[NewsItem]:
    """Every article fetched for this ticker on this specific date (already
    capped to FETCH_LIMIT at fetch time) — no 'nearest available' fallback
    like price/fx, since news only exists for days a fetch actually ran.
    Empty if nothing was fetched that day."""
    return list(
        NewsItem.select()
        .where(NewsItem.ticker == ticker, NewsItem.fetched_date == fetched_date)
        .order_by(NewsItem.published_at.desc())
    )
