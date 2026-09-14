from functools import lru_cache

from supabase import Client as SupabaseClient
from supabase import create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> SupabaseClient:
    """Service-role client. Backend-only — never expose this key to the frontend."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
