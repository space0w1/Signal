from peewee import CharField, CompositeKey, DateField, FloatField

from app.models.base import BaseModel


class WorldMarketPrice(BaseModel):
    """Daily close per world-market index/ETF (see services/world_markets.py).
    Kept apart from price_history on purpose: a few of these are ETFs someone
    could also hold, and rows here must not make add_holding() think such a
    ticker was already backfilled."""

    symbol = CharField()
    date = DateField()
    close = FloatField()

    class Meta:
        table_name = "world_market_prices"
        primary_key = CompositeKey("symbol", "date")
