from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ACCESS_SECRET: str = "change_me_access_secret"
    SECRET_KEY: str = "change_me_secret_key"
    SERVER_ENVIRONMENT: str = "development"
    CORE_BASE_URL: str = "http://localhost:8001"
    REDIS_DSN: str = "localhost:6379"
    REDIS_PASSWORD: str = ""
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "allow"}


settings = Settings()
