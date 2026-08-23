from peewee import BooleanField, CharField, DateField, FloatField, ForeignKeyField

from app.models.base import BaseModel
from app.models.user import User


class Holding(BaseModel):
    """One row per ticker per user. Cost basis is cumulative (not lot-level):
    total_quantity/total_cost are running totals, average price is derived.

    Soft-deleted (is_active=False, removed_date stamped) rather than deleted,
    so past date-picker snapshots stay honest about what was held when.
    """

    user = ForeignKeyField(User, backref="holdings")
    ticker = CharField()
    exchange = CharField()
    currency = CharField()
    total_quantity = FloatField()
    total_cost = FloatField()
    date_added = DateField()
    is_active = BooleanField(default=True)
    removed_date = DateField(null=True)

    class Meta:
        table_name = "holdings"
        indexes = (
            (("user", "ticker"), True),
            (("user", "is_active"), False),
        )
