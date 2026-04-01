from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://webhook_user:webhook_pass@db:5432/webhook_db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Security
    SECRET_KEY: str = "supersecretkey123"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Anthropic
    GROQ_API_KEY: str = ""
    
    # Webhook delivery settings
    MAX_RETRY_ATTEMPTS: int = 5
    BASE_RETRY_DELAY: int = 30        # seconds
    MAX_RETRY_DELAY: int = 7200       # 2 hours
    DELIVERY_TIMEOUT: int = 30        # seconds
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()