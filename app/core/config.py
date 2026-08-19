"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "EGO Marketplace API"
    ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS - comma-separated list of allowed origins in the environment,
    # e.g. "http://localhost:3000,https://app.example.com"
    BACKEND_CORS_ORIGINS: str = ""

    # --- Database (Supabase PostgreSQL) ---
    # Full connection string as given by Supabase, e.g.:
    #   postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
    # The "postgresql://" / "postgres://" scheme is normalized to the asyncpg
    # driver at use (see `sqlalchemy_database_url` below) - no need to edit it.
    DATABASE_URL: str

    # Supabase enforces SSL on connections from outside its network. Keep this
    # True for Supabase; set False only for a local/non-TLS Postgres.
    DB_SSL_REQUIRE: bool = True

    # Supabase offers two connection modes with different pooling needs:
    #   "session"     - direct connection (port 5432) or Supavisor session
    #                    pooler. Behaves like a normal Postgres connection, so
    #                    SQLAlchemy manages its own connection pool.
    #   "transaction" - Supavisor transaction pooler (port 6543). The pooler
    #                    itself multiplexes connections and does not support
    #                    server-side prepared statements, so SQLAlchemy must
    #                    use NullPool and asyncpg's statement cache is disabled.
    DB_POOL_MODE: Literal["session", "transaction"] = "session"

    # Pool sizing (only applies when DB_POOL_MODE="session"). Supabase's free
    # and small tiers cap total Postgres connections quite low, so keep this
    # conservative relative to the number of backend instances you run.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    # Recycle pooled connections periodically so the app doesn't hand out a
    # connection Supabase's network layer has silently dropped while idle.
    DB_POOL_RECYCLE: int = 1800

    DB_ECHO: bool = False

    # --- Firebase Admin SDK (server-side ID token verification only) ---
    # Exactly one of these should be set. Never commit the underlying
    # service-account JSON - see .gitignore and docs/authentication.md.
    #   FIREBASE_CREDENTIALS_JSON - the full service-account JSON, as a
    #     single-line string (e.g. how you'd set a secret on most hosting
    #     platforms that don't let you mount a file).
    #   FIREBASE_CREDENTIALS_FILE - a filesystem path to a service-account
    #     JSON file (for local development).
    FIREBASE_CREDENTIALS_JSON: str | None = None
    FIREBASE_CREDENTIALS_FILE: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """DATABASE_URL rewritten to use the asyncpg driver SQLAlchemy needs."""
        url = self.DATABASE_URL
        for scheme in ("postgresql://", "postgres://"):
            if url.startswith(scheme):
                return url.replace(scheme, "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
