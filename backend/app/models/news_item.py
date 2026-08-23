from peewee import CharField, DateField, DateTimeField, TextField

from app.models.base import BaseModel


class NewsItem(BaseModel):
    """Raw news per ticker, fetched via yfinance's `.news`. fetched_date
    ties each batch to the day it came in — the SAME article can appear
    on yfinance's feed across multiple days, and each of those days gets
    its own row (unique per ticker+url+fetched_date, not per ticker+url),
    so that querying a specific past date returns exactly what was fetched
    that day, not a deduplicated all-time list."""

    ticker = CharField()
    headline = TextField()
    source = CharField(null=True)
    url = TextField(null=True)
    thumbnail_url = TextField(null=True)
    article_text = TextField(null=True)  # extracted via trafilatura; context for the AI summary
    published_at = DateTimeField(null=True)
    fetched_date = DateField()

    class Meta:
        table_name = "news_items"
        indexes = (
            (("ticker", "url", "fetched_date"), True),
            (("ticker", "fetched_date"), False),
        )
