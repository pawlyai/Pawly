from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    telegram_bot_token: str
    google_api_key: str
    google_maps_api_key: str = ""
    node_env: str = "development"
    port: int = 8000
    log_level: str = "info"
    main_model: str = "gemini-2.0-flash"
    extraction_model: str = "gemini-2.0-flash"
    fallback_model: str = "gemini-2.0-flash"  # used when main_model exhausts retries
    max_turns_in_context: int = 5
    max_messages_per_minute: int = 30
    webhook_host: str = ""  # e.g. "api.pawly.app" - required in production
    miniapp_api_url: str = "https://api.pawly.app"  # override for local dev (e.g. ngrok URL)
    telegram_proxy_url: str = ""
    admin_telegram_ids: str = ""
    prompt_hot_reload: bool = False
    use_langgraph: bool = False  # set True to enable LangGraph pipeline (experimental)

    # Alternative LLM providers (optional — only needed if using Claude or DeepSeek models)
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""

    # Langfuse observability (optional — tracing degrades gracefully when absent)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse-server:3000"

    model_config = ConfigDict(env_file=".env")


settings = Settings()

