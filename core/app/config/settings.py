from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "skill_db"
    EMAIL_GHUPSHAP_KEY: str = ""
    SERVER_ENVIRONMENT: str = "development"

    model_config = {"env_file": ".env", "extra": "allow"}


settings = Settings()
