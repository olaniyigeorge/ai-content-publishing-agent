from fastapi import APIRouter, Depends

from app.services.intake_service import create_content_request
from app.services.request_state_service import list_content_requests
from auth.deps import get_current_user
from shared.models import ContentRequestCreate, ContentRequestOut

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=ContentRequestOut)
def post_request(body: ContentRequestCreate, user: dict = Depends(get_current_user)) -> ContentRequestOut:
    return create_content_request(body, submitted_by_user_id=str(user["id"]))


@router.get("", response_model=list[ContentRequestOut])
def get_requests(user: dict = Depends(get_current_user)) -> list[ContentRequestOut]:
    return list_content_requests()
