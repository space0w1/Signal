from pathlib import Path

from peewee import SqliteDatabase

from app.core.config import settings

Path("data").mkdir(exist_ok=True)

db_path = settings.database_url.removeprefix("sqlite:///")
database = SqliteDatabase(db_path)
