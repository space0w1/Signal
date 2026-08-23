from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Signal"
    database_url: str = "sqlite:///./data/signal.db"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
