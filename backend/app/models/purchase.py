from peewee import DateField, FloatField, ForeignKeyField

from app.models.base import BaseModel
from app.models.holding import Holding


class Purchase(BaseModel):
    """One row per buy. Source of truth for point-in-time reconstruction —
    holdings.total_quantity/total_cost are just a cache of SUM(purchases)
    recomputed on every write, not incremented directly, so a past-date
    portfolio query can replay only the purchases that existed by then."""

    holding = ForeignKeyField(Holding, backref="purchases")
    quantity = FloatField()
    price = FloatField()  # per-share, native currency
    purchase_date = DateField()

    class Meta:
        table_name = "purchases"
        indexes = ((("holding", "purchase_date"), False),)
