from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    ENVIRONMENT: str
    DATABASE_URL: str

    #Required for render deployment  
    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    REDIS_URL: str
    SECRET_KEY: str
    GROQ_API_KEY: str
    FRONTEND_URL: str = ""

    @property
    def cors_origins(self) -> list[str]:
        origins = ["http://localhost:3000"] if self.ENVIRONMENT == "development" else []
        if self.FRONTEND_URL:
            origins.append(self.FRONTEND_URL)
        return origins

    # Webhook Delivery Settings
    MAX_RETRY_ATTEMPTS: int = 5
    BASE_RETRY_DELAY: int = 30        # seconds — delay before first retry
    MAX_RETRY_DELAY: int = 7200       # 2 hours — cap on exponential backoff
    DELIVERY_TIMEOUT: int = 30        # seconds — per HTTP request

    model_config = SettingsConfigDict()


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
