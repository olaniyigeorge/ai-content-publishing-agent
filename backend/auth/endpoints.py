from fastapi import APIRouter, Depends, Response

from app.config import get_settings
from auth.deps import get_current_user, get_session_id
from auth.models import (
    AccessRuleIn,
    AccessRuleOut,
    MeResponse,
    RequestCodeRequest,
    RequestCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from auth.service import logout, request_code, verify_code
from db.client import get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-code", response_model=RequestCodeResponse)
def post_request_code(body: RequestCodeRequest) -> RequestCodeResponse:
    request_code(body.email)
    return RequestCodeResponse()


@router.post("/verify-code", response_model=VerifyCodeResponse)
def post_verify_code(body: VerifyCodeRequest, response: Response) -> VerifyCodeResponse:
    settings = get_settings()
    session_id = verify_code(body.email, body.code)
    # Frontend (Vercel) and backend (Render) are different sites in
    # production, so the session cookie must be sent cross-site — that
    # requires SameSite=None, which browsers only honor alongside Secure.
    # Locally both run on localhost (same site, just different ports), where
    # Lax works fine and Secure isn't available over plain http.
    is_cross_site = settings.environment != "development"
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=is_cross_site,
        samesite="none" if is_cross_site else "lax",
        max_age=settings.session_ttl_minutes * 60,
    )
    return VerifyCodeResponse()


@router.post("/logout")
def post_logout(response: Response, session_id: str = Depends(get_session_id)) -> dict:
    settings = get_settings()
    logout(session_id)
    response.delete_cookie(settings.session_cookie_name)
    return {"message": "logged out"}


@router.get("/me", response_model=MeResponse)
def get_me(user: dict = Depends(get_current_user)) -> MeResponse:
    return MeResponse(**user)


# --- admin: access_rules CRUD (any authenticated user for v1 — no separate
# admin role exists yet; restrict this route at the infra/proxy layer if
# exposing it beyond trusted operators). ---


@router.get("/access-rules", response_model=list[AccessRuleOut])
def list_access_rules(user: dict = Depends(get_current_user)) -> list[dict]:
    return get_supabase().table("access_rules").select("*").order("created_at", desc=True).execute().data


@router.post("/access-rules", response_model=AccessRuleOut)
def create_access_rule(body: AccessRuleIn, user: dict = Depends(get_current_user)) -> dict:
    payload = body.model_dump(mode="json")
    payload["value"] = payload["value"].strip().lower()
    return get_supabase().table("access_rules").insert(payload).execute().data[0]


@router.delete("/access-rules/{rule_id}")
def delete_access_rule(rule_id: str, user: dict = Depends(get_current_user)) -> dict:
    get_supabase().table("access_rules").delete().eq("id", rule_id).execute()
    return {"message": "deleted"}
