from peewee import CharField, DateField, DateTimeField, TextField

from app.models.base import BaseModel


class NewsItem(BaseModel):
    """Raw news per ticker, fetched nightly via yfinance's `.news`.
    fetched_date ties each batch to the cron day it came in."""

    ticker = CharField()
    headline = TextField()
    source = CharField(null=True)
    url = TextField(null=True)
    published_at = DateTimeField(null=True)
    fetched_date = DateField()

    class Meta:
        table_name = "news_items"
        indexes = (
            (("ticker", "url"), True),
            (("ticker", "fetched_date"), False),
        )
