from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    telegram_bot_token: str
    anthropic_api_key: str
    google_maps_api_key: str = ""
    node_env: str = "development"
    port: int = 8000
    log_level: str = "info"
    main_model: str = "claude-sonnet-4-20250514"
    extraction_model: str = "claude-haiku-4-5-20251001"
    max_turns_in_context: int = 5
    max_messages_per_minute: int = 30
    webhook_host: str = ""  # e.g. "api.pawly.app" — required in production

    class Config:
        env_file = ".env"


settings = Settings()
