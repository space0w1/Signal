from datetime import datetime

from peewee import DateTimeField

from app.models.base import BaseModel


class User(BaseModel):
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "users"
