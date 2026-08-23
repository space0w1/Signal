from peewee import CharField, DateField, FloatField, ForeignKeyField

from app.models.base import BaseModel
from app.models.holding import Holding


class Transaction(BaseModel):
    """One row per buy or sell. Source of truth for cost basis and PnL —
    holdings.total_quantity/total_cost/realized_pnl are a cache recomputed
    from this via a chronological replay. Order matters once sells exist
    (unlike buy-only accumulation): each sell's cost-basis reduction depends
    on the average cost immediately before it, not a simple aggregate."""

    holding = ForeignKeyField(Holding, backref="transactions")
    type = CharField()  # 'buy' | 'sell'
    quantity = FloatField()  # always positive; type determines direction
    price = FloatField()  # per-share, native currency
    transaction_date = DateField()

    class Meta:
        table_name = "transactions"
        indexes = ((("holding", "transaction_date"), False),)
