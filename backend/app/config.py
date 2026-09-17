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

    job_stale_processing_seconds: int = 600
    """EDGE_CASES.md #61: a job whose worker process died mid-handler (OOM,
    redeploy, SIGKILL) between claiming it and marking it succeeded/failed is
    left at status='processing' forever — nothing else ever revisits it. Kept
    in sync with the same interval hardcoded in claim_pending_job()
    (alembic/versions/0007_reclaim_stale_jobs.py), which reclaims it back to
    pending/failed on the DB side; this setting is the app-layer mirror used
    by job_guard.has_pending_revision so a stuck row doesn't also permanently
    block regenerating the draft it targeted while waiting for the worker's
    next poll to reclaim it."""
    max_revisions: int = 3
    """EDGE_CASES.md #24: hard cap on the evaluate->generate revision loop so
    a draft that never clears the rubric doesn't burn Claude calls forever."""

    max_gap_fill_attempts: int = 2
    """Cap on how many extra, evaluation-informed web searches a request
    without a user-supplied source URL gets when a draft's grounding comes
    back empty or thin. Bounded separately from max_revisions so a search
    that finds nothing useful doesn't also burn the revision cap."""

    session_cookie_name: str = "koya_session"
    session_ttl_minutes: int = 60
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5

    resend_api_key: str
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
