"""
Centralized Configuration System
Loads and validates environment variables using Pydantic Settings.
"""

from functools import lru_cache
from typing import List, Literal, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    APP_ENV: Literal["development", "testing", "production"] = "development"
    APP_NAME: str = "Paradox Sports OMS"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = False

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Security & Allowed Hosts / CORS
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-me-in-production",
        description="Application secret key for cryptographic operations",
    )
    ALLOWED_HOSTS: Union[str, List[str]] = Field(
        default=["*"],
        description="List of allowed hostnames/IPs for TrustedHostMiddleware",
    )
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default=["*"],
        description="List of allowed origins for CORSMiddleware",
    )
    ENABLE_SECURITY_HEADERS: bool = Field(
        default=True,
        description="Enable CSP, HSTS, X-Frame-Options, and nosniff headers",
    )
    ENFORCE_HTTPS: bool = Field(
        default=False,
        description="Enforce Strict-Transport-Security (HSTS) header in production",
    )

    # API Documentation Security (HTTP Basic Auth for /docs, /redoc, /openapi.json)
    API_DOCS_USERNAME: str = Field(
        default="docs_admin",
        description="HTTP Basic Auth username for API documentation access",
    )
    API_DOCS_PASSWORD: str = Field(
        default="DocsAdminPassword@123",
        description="HTTP Basic Auth password for API documentation access",
    )
    ENABLE_DOCS: bool = Field(
        default=True,
        description="Enable restricted /docs, /redoc, and /openapi.json endpoints",
    )

    # Rate Limiting (In-Memory Sliding Window, Requests per Minute)
    RATE_LIMIT_LOGIN_PER_MINUTE: int = Field(default=10, ge=1, le=100)
    RATE_LIMIT_GLOBAL_PER_MINUTE: int = Field(default=120, ge=10, le=1000)

    # PostgreSQL Database Connection
    DATABASE_URL: str = Field(
        ...,
        description="Authoritative PostgreSQL Connection URL (postgresql://user:pass@host:port/dbname)",
    )

    # Database Connection Pool Settings
    DATABASE_POOL_SIZE: int = Field(default=10, ge=1, le=50)
    DATABASE_MAX_OVERFLOW: int = Field(default=20, ge=0, le=50)
    DATABASE_POOL_TIMEOUT: int = Field(default=30, ge=1, le=120)
    DATABASE_POOL_RECYCLE: int = Field(default=1800, ge=60, le=7200)

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Session & Authentication Configuration
    SESSION_COOKIE_NAME: str = "oms_session"
    SESSION_EXPIRE_HOURS: int = Field(default=24, ge=1, le=720)
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # Development Seed (Dev only)
    DEV_ADMIN_USERNAME: str = "admin"
    DEV_ADMIN_PASSWORD: str = "AdminPassword@123"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError(
                "DATABASE_URL must be a valid PostgreSQL connection string starting with "
                "'postgresql://' or 'postgresql+psycopg2://'. SQLite or other engines are not permitted."
            )
        return v

    @field_validator("ALLOWED_HOSTS", "CORS_ORIGINS", mode="before")
    @classmethod
    def parse_list_from_str(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG mode must be disabled in production (DEBUG=False).")
            if (
                "change-me" in self.SECRET_KEY.lower()
                or "dev-secret" in self.SECRET_KEY.lower()
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError(
                    "SECRET_KEY must be a strong, cryptographically secure string (min 32 chars) "
                    "and cannot use default development keys in production."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached instance of validated application settings."""
    return Settings()
