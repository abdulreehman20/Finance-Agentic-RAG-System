"""Application configuration.

All environment variables are loaded and validated here via
``pydantic-settings``. Never read ``os.environ`` directly elsewhere in the
codebase; import :data:`settings` instead.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(
        default="",
        description="Async SQLAlchemy connection URL (must use the asyncpg driver).",
    )

    # AuthLib
    JWT_SECRET: str = Field(default="", description="JWT secret.")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm.")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="JWT access token expire minutes.")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="JWT refresh token expire days.")

    # Starlette session cookie
    SESSION_SECRET: str = Field(default="", description="Session secret.")
    SESSION_COOKIE_NAME: str = Field(default="app_session", description="Session cookie name.")
    SESSION_MAX_AGE: int = Field(default=86400, description="Session max age.")

    APP_BASE_URL: str = Field(default="", description="App base URL.")
    PORT: int = Field(default=8000, description="Port to run the app on.")

    # Sentry
    SENTRY_DSN: str = Field(default="", description="Sentry DSN.")

    # Runtime
    ENVIRONMENT: str = Field(
        default="development", description="Deployment environment name."
    )
    DEBUG: bool = Field(default=False, description="Enable debug behaviour.")

    # Backwards-compatible attribute names (existing code uses these)
    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET

    @property
    def jwt_algorithm(self) -> str:
        return self.JWT_ALGORITHM
    
    @property
    def jwt_access_token_expire_minutes(self) -> int:
        return self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    
    @property
    def jwt_refresh_token_expire_days(self) -> int:
        return self.JWT_REFRESH_TOKEN_EXPIRE_DAYS

    @property
    def session_secret(self) -> str:
        return self.SESSION_SECRET
    
    @property
    def session_cookie_name(self) -> str:
        return self.SESSION_COOKIE_NAME
    
    @property
    def session_max_age(self) -> int:
        return self.SESSION_MAX_AGE
    
    @property
    def app_base_url(self) -> str:
        return self.APP_BASE_URL
    
    @property
    def port(self) -> int:
        return self.PORT

    @property
    def sentry_dsn(self) -> str:
        return self.SENTRY_DSN

    @property
    def environment(self) -> str:
        return self.ENVIRONMENT

    @property
    def debug(self) -> bool:
        return self.DEBUG

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production" 


@lru_cache()
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()


settings = get_settings()
