from peewee import CharField, CompositeKey, DateField, FloatField

from app.models.base import BaseModel


class SectorFundDay(BaseModel):
    """Daily NAV and shares outstanding per sector ETF, from State Street's NAV
    history files (see services/sector_flows.py). Net flows are derived from the
    day-to-day change in shares, so this is stored instead of a close price."""

    symbol = CharField()
    date = DateField()
    nav = FloatField()
    shares = FloatField()
    total_net_assets = FloatField()

    class Meta:
        table_name = "sector_fund_days"
        primary_key = CompositeKey("symbol", "date")
