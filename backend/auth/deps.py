from fastapi import Cookie, Depends, HTTPException

from app.config import get_settings
from auth.service import get_user_for_session

_settings = get_settings()


def get_session_id(session: str | None = Cookie(default=None, alias=_settings.session_cookie_name)) -> str:
    if session is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return session


def get_current_user(session_id: str = Depends(get_session_id)) -> dict:
    """FastAPI dependency: looks up the session cookie on every protected
    route. This is the access-control gate — there is no Supabase RLS, this
    function is the only thing standing between a request and the data."""
    user = get_user_for_session(session_id)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user
