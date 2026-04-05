from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://webhook_user:webhook_pass@db:5432/webhook_db"

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
        
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "supersecretkey123"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Groq — AI failure analysis
    GROQ_API_KEY: str = ""

    # Webhook delivery settings
    MAX_RETRY_ATTEMPTS: int = 5
    BASE_RETRY_DELAY: int = 30        # seconds — delay before first retry
    MAX_RETRY_DELAY: int = 7200       # 2 hours — cap on exponential backoff
    DELIVERY_TIMEOUT: int = 30        # seconds — per HTTP request

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()