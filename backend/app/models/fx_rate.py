from peewee import CharField, CompositeKey, DateField, FloatField

from app.models.base import BaseModel


class FxRate(BaseModel):
    """One row per currency pair per day, refreshed once nightly by cron.
    Only USD->SGD and HKD->SGD are tracked; SG holdings need no conversion."""

    date = DateField()
    currency_pair = CharField()
    rate = FloatField()

    class Meta:
        table_name = "fx_rates"
        primary_key = CompositeKey("date", "currency_pair")
