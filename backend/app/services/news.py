import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import trafilatura
import yfinance as yf

from app.db import database
from app.models import NewsItem

logger = logging.getLogger(__name__)

FETCH_LIMIT = 5  # matches what the AI summary will use as citation candidates

RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
RSS_TIMEOUT_SECONDS = 15
CARRY_FORWARD_MAX_AGE_DAYS = 3  # oldest article worth re-serving when live sources are down


class NewsUnavailableError(Exception):
    pass


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


def _fetch_yfinance_items(ticker: str) -> list[dict]:
    """News via yfinance's `.news`, normalized across its old/new schema
    variants (see backend/tests/test_yahoo.py, which prototyped this same
    normalization for article-text extraction). Without article_text."""
    stock = yf.Ticker(ticker)
    raw_items = stock.news or []

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
                "published_at": _parse_published_at(item),
            }
        )

    return normalized


def _strip_rss_tracking(url: str) -> str:
    """Drops the `.tsrc=rss` tracking param Yahoo appends to every RSS link, so
    an article's url matches what the yfinance path would have stored."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != ".tsrc"]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _parse_rss_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def _fetch_rss_items(ticker: str) -> list[dict]:
    """Yahoo's per-ticker RSS headline feed, the fallback for when yfinance's
    news endpoint comes back short. It carries no publisher or thumbnail, so
    source is the article's domain and thumbnail_url is left empty. Items
    aren't strictly date-ordered in the feed, hence the sort."""
    request = urllib.request.Request(
        RSS_URL.format(ticker=ticker), headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=RSS_TIMEOUT_SECONDS) as response:
        root = ET.fromstring(response.read())

    items = []
    for node in root.iter("item"):
        link = (node.findtext("link") or "").strip()
        url = _strip_rss_tracking(link) if link else None
        items.append(
            {
                "headline": (node.findtext("title") or "").strip() or "No Title",
                "source": urlsplit(url).hostname.removeprefix("www.") if url else None,
                "url": url,
                "thumbnail_url": None,
                "published_at": _parse_rss_date(node.findtext("pubDate")),
            }
        )

    items.sort(key=lambda i: i["published_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


def _add_new(items: list[dict], candidates: list[dict]) -> int:
    """Appends candidates to items, skipping url-less ones and urls already
    present, until items holds FETCH_LIMIT. Returns how many were added. Earlier
    sources keep their place — later ones only fill what's left."""
    seen = {item["url"] for item in items}
    added = 0
    for candidate in candidates:
        if len(items) >= FETCH_LIMIT:
            break
        url = candidate["url"]
        if not url or url in seen:
            continue
        items.append(candidate)
        seen.add(url)
        added += 1
    return added


def fetch_news(ticker: str) -> list[dict]:
    """Up to FETCH_LIMIT live news items for a ticker, with article text.

    yfinance first, then Yahoo's RSS feed to fill whatever yfinance left short.
    The yfinance endpoint intermittently 404s, and yfinance turns that into an
    empty list rather than an exception — so being short is treated as a source
    problem, not as "no news today". Never raises: a source that errors just
    contributes nothing."""
    items: list[dict] = []
    for name, source in (("yfinance", _fetch_yfinance_items), ("RSS", _fetch_rss_items)):
        if len(items) >= FETCH_LIMIT:
            break
        try:
            candidates = source(ticker)
        except Exception as exc:
            logger.warning("%s: %s news failed (%s: %s)", ticker, name, type(exc).__name__, exc)
            continue
        added = _add_new(items, candidates)
        if name != "yfinance":
            logger.info("%s: topped up with %d item(s) from %s", ticker, added, name)

    for item in items:
        item["article_text"] = _fetch_article_text(item["url"])
    return items


def _carry_forward_items(ticker: str, today: date) -> list[dict]:
    """Articles from earlier fetches, newest first, for filling today's set
    when the live sources came up short. Only articles published within
    CARRY_FORWARD_MAX_AGE_DAYS qualify, which is what stops a multi-day outage
    from re-serving the same week-old articles indefinitely (a carried row looks
    like any other row to the next day's carry-forward); rows with no
    published_at can't be aged, so they're excluded too. The same article
    usually exists under several fetched_dates — _add_new dedupes by url."""
    cutoff = datetime.now() - timedelta(days=CARRY_FORWARD_MAX_AGE_DAYS)
    previous = (
        NewsItem.select()
        .where(
            NewsItem.ticker == ticker,
            NewsItem.fetched_date < today,
            NewsItem.published_at >= cutoff,
        )
        .order_by(NewsItem.published_at.desc(), NewsItem.fetched_date.desc())
    )
    return [
        {
            "headline": item.headline,
            "source": item.source,
            "url": item.url,
            "thumbnail_url": item.thumbnail_url,
            "article_text": item.article_text,
            "published_at": item.published_at,
        }
        for item in previous
    ]


def refresh_news(ticker: str) -> int:
    """Fetches today's news for a ticker and records it under today's
    fetched_date. An article already seen on a previous fetch still gets
    a fresh row for today (see NewsItem docstring) — a past-date query
    should show exactly what was served that day.

    Always aims for FETCH_LIMIT articles: live sources first (see fetch_news),
    then recent articles from earlier fetches to fill the rest, so the nightly
    summary has a full set to cite. If even that yields nothing, this raises:
    the nightly job then marks the ticker stale and skips caching its summary,
    rather than pinning a news-less one to today."""
    today = date.today()
    items = fetch_news(ticker)
    live = len(items)
    if live < FETCH_LIMIT:
        carried = _add_new(items, _carry_forward_items(ticker, today))
        if carried:
            logger.warning("%s: %d live article(s), filled %d from earlier fetches", ticker, live, carried)

    if not items:
        raise NewsUnavailableError(
            f"{ticker}: no live news and nothing from the last "
            f"{CARRY_FORWARD_MAX_AGE_DAYS} days to carry forward"
        )

    rows = [{**item, "ticker": ticker, "fetched_date": today} for item in items]
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
