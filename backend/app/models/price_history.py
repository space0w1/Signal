from peewee import CharField, CompositeKey, DateField, FloatField

from app.models.base import BaseModel


class PriceHistory(BaseModel):
    """Daily close price per ticker. Backfilled 5yr once when a ticker is first
    added, then one row appended per ticker per night by cron."""

    ticker = CharField()
    date = DateField()
    close_price = FloatField()
    currency = CharField()

    class Meta:
        table_name = "price_history"
        primary_key = CompositeKey("ticker", "date")
