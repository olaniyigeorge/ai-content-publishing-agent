from functools import lru_cache

import httpx
from supabase import Client as SupabaseClient
from supabase import ClientOptions, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> SupabaseClient:
    """
    Service-role client. Backend-only — never expose this key to the frontend.

    Forces HTTP/1.1: HTTP/2 long-lived connections through this stack have
    been observed dropping mid-request with `SSLV3_ALERT_BAD_RECORD_MAC`
    (seen in local/WSL2 networking), which can abort a multi-step service
    function (e.g. intake_service.create_content_request) partway through
    and leave an orphaned row with no follow-up job. HTTP/1.1 avoids the
    long-lived multiplexed connection that triggers it.

    keepalive_expiry is set well below Supabase/any intermediate proxy's idle
    timeout so httpx retires pooled connections before the network path
    silently drops them — an idle connection handed back out for reuse after
    the far end has closed it is what previously surfaced as
    `SSL: UNEXPECTED_EOF_WHILE_READING` on `/auth/request-code`. The
    transport-level retry is a second layer: if a connection still goes
    stale between the expiry check and use, one retry on a fresh connection
    absorbs it instead of bubbling up as a 500.
    """
    settings = get_settings()
    httpx_client = httpx.Client(
        http2=False,
        timeout=30,
        limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=15),
        transport=httpx.HTTPTransport(retries=1),
    )
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(httpx_client=httpx_client),
    )
