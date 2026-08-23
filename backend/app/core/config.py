from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Signal"
    database_url: str = "postgresql://signal:signal@db:5432/signal"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
