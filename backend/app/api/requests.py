from fastapi import APIRouter, Depends

from app.services.request_state_service import get_content_request_detail
from auth.deps import get_current_user
from shared.models import ContentRequestDetail

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.get("/{request_id}", response_model=ContentRequestDetail)
def get_request_detail(request_id: str, user: dict = Depends(get_current_user)) -> ContentRequestDetail:
    return get_content_request_detail(request_id)
