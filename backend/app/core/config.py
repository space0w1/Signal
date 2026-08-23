from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Signal"
    database_url: str = "postgresql://signal:signal@db:5432/signal"
    cors_origins: list[str] = ["http://localhost:5173"]

    llm_provider: str = "gemini"  # "anthropic" | "gemini"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    class Config:
        env_file = ".env"


settings = Settings()
