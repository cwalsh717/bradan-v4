from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@host:port/dbname"
    TWELVE_DATA_API_KEY: str = ""
    FRED_API_KEY: str = ""
    APP_ENV: str = "development"

    model_config = {"env_file": ".env"}


settings = Settings()
