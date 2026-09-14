from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str
    supabase_db_url: str

    anthropic_api_key: str
    firecrawl_api_key: str

    worker_poll_interval_seconds: int = 5
    job_max_attempts: int = 3
    queue_max_attempts: int = 3
    max_revisions: int = 3
    """EDGE_CASES.md #24: hard cap on the evaluate->generate revision loop so
    a draft that never clears the rubric doesn't burn Claude calls forever."""

    session_cookie_name: str = "koya_session"
    session_ttl_minutes: int = 60
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5

    resend_api_key: str = ""
    email_from_address: str = "email@from.com"
    email_from_name: str = "Koya Talent"

    environment: str = "development"
    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_db_url(self) -> str:
        """Supabase's dashboard hands you a plain `postgresql://` connection
        string, which SQLAlchemy defaults to the psycopg2 driver — but this
        project installs psycopg (v3). Normalize the scheme here so pasting
        Supabase's URL as-is into .env just works, instead of requiring
        everyone to remember to add `+psycopg` by hand."""
        url = self.supabase_db_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
