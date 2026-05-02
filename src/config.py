from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    telegram_bot_token: str
    google_api_key: str
    google_maps_api_key: str = ""
    # Optional — required only when evaluating Claude / GPT / DeepSeek models in the test runner
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
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

    # Langfuse observability (optional — tracing degrades gracefully when absent)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse-server:3000"

    # Support email (SMTP) — leave smtp_host empty to disable email sending
    support_email: str = "internal_tech@pawlyai.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # defaults to smtp_user if empty

    model_config = ConfigDict(env_file=".env")


settings = Settings()

