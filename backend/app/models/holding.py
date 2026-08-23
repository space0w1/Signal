from peewee import BooleanField, CharField, DateField, FloatField, ForeignKeyField

from app.models.base import BaseModel
from app.models.user import User


class Holding(BaseModel):
    """One row per ticker per user. total_quantity/total_cost/realized_pnl
    are a cache — derived from replaying this holding's `transactions`
    (the source of truth) — recomputed on every write, never mutated
    directly. Average price is total_cost / total_quantity, never stored.

    Soft-deleted (is_active=False, removed_date stamped) rather than
    deleted — either explicitly, or automatically once a sell brings
    total_quantity to zero — so past date-picker snapshots stay honest
    about what was held when.
    """

    user = ForeignKeyField(User, backref="holdings")
    ticker = CharField()
    exchange = CharField()
    currency = CharField()
    total_quantity = FloatField()
    total_cost = FloatField()
    realized_pnl = FloatField(default=0)
    date_added = DateField()
    is_active = BooleanField(default=True)
    removed_date = DateField(null=True)

    class Meta:
        table_name = "holdings"
        indexes = (
            (("user", "ticker"), True),
            (("user", "is_active"), False),
        )
