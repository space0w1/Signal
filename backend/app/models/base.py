from peewee import Model

from app.db import database


class BaseModel(Model):
    class Meta:
        database = database
