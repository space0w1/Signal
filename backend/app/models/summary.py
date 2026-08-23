from peewee import CharField, DateField, DateTimeField, ForeignKeyField, TextField

from app.models.base import BaseModel
from app.models.user import User


class Summary(BaseModel):
    """One row per (target, date) — never overwritten, so past date-picker
    snapshots stay retrievable. ticker holds the actual ticker for
    target_type='stock', or the '__portfolio__' sentinel for
    target_type='portfolio' (SQLite treats each NULL as distinct in a UNIQUE
    constraint, so NULL wouldn't actually enforce one-row-per-date there).
    """

    user = ForeignKeyField(User, backref="summaries")
    target_type = CharField()
    ticker = CharField()
    date = DateField()
    summary_text = TextField()
    cited_news_ids = TextField(null=True)
    generated_at = DateTimeField()

    class Meta:
        table_name = "summaries"
        indexes = ((("user", "target_type", "ticker", "date"), True),)
