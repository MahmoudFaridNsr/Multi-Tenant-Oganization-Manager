from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:123456@localhost:5432/org_manager"
    jwt_secret_key: str = "TaRyW0EvUb1tZLanQOIKagifbijJ4Q8NQju7BYyTPgX"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_hash_iterations: int = 210_000

    gemini_api_key: str = "AIzaSyCulVGSeNaDyhUPSsZ6Qx5zTzYosTUi5yQ"
    gemini_model: str = "gemini-flash-latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()
