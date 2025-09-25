from pathlib import Path

from decouple import config
from pydantic_settings import BaseSettings

# Use this to build paths inside the project
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Class to hold application's config values."""

    APP_NAME: str = config("APP_NAME", default="TensorZero Livekit Agent")
    APP_VERSION: str = config("APP_VERSION", default="0.1.0")
    APP_DESCRIPTION: str = config("APP_DESCRIPTION", default="TensorZero Livekit Agent")
    ENVIRONMENT: str = config("ENVIRONMENT", default="development")
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")

    OPENAI_API_KEY: str = config("OPENAI_API_KEY", default="")
    GOOGLE_AI_STUDIO_API_KEY: str = config("GOOGLE_AI_STUDIO_API_KEY", default="")

    GOOGLE_APPLICATION_CREDENTIALS: str = config(
        "GOOGLE_APPLICATION_CREDENTIALS", default=""
    )

    LIVEKIT_AGENT: str = config("LIVEKIT_AGENT", default="t0-ai-agent-local")
    LIVEKIT_URL: str = config("LIVEKIT_URL", default="wss://livekit.outbound.im")
    LIVEKIT_API_KEY: str = config("LIVEKIT_API_KEY", default="APITpQ4nBVwiwZY")
    LIVEKIT_API_SECRET: str = config("LIVEKIT_API_SECRET", default="ZcmuXyVRzU31YABGDT9IixXaYjr5YsnOQZ4gKVlelZF")

    # TensorZero
    CLICKHOUSE_USER: str = config("CLICKHOUSE_USER", default="chuser")
    CLICKHOUSE_PASSWORD: str = config("CLICKHOUSE_PASSWORD", default="chpassword")
    CLICKHOUSE_HOST: str = config("CLICKHOUSE_HOST", default="localhost")
    CLICKHOUSE_PORT: int = config("CLICKHOUSE_PORT", default=8123)
    CLICKHOUSE_DATABASE: str = config("CLICKHOUSE_DATABASE", default="tensorzero")
    TENSORZERO_GATEWAY_URL: str = config("TENSORZERO_GATEWAY_URL", default="http://localhost:3000")

    @property
    def CLICKHOUSE_URL(self):
        return f"http://{self.CLICKHOUSE_USER}:{self.CLICKHOUSE_PASSWORD}@{self.CLICKHOUSE_HOST}:{self.CLICKHOUSE_PORT}/{self.CLICKHOUSE_DATABASE}"


settings = Settings()
