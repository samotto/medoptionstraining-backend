from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/medoptionstraining"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    seed_admin_email: str = "sam@overturegroup.com"
    seed_admin_password: str = "abc"
    seed_admin_force_password_reset: bool = False
    resend_api_key: str = ""
    email_from: str = "Med Options Training <onboarding@resend.dev>"
    frontend_url: str = "http://localhost:5173"
    email_verification_minutes: int = 60
    app_timezone: str = "America/Chicago"

    @property
    def allowed_frontend_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.frontend_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
