from playhouse.db_url import connect

from app.core.config import settings

database = connect(settings.database_url)


def init_db() -> None:
    from app.models import ALL_MODELS

    database.connect(reuse_if_open=True)
    database.create_tables(ALL_MODELS)
    database.close()
