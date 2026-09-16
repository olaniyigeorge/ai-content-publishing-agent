from fastapi import APIRouter, Depends

from app.services.request_state_service import get_content_request_detail, override_source_status
from auth.deps import get_current_user
from shared.models import ContentRequestDetail, SourceOut, SourceOverrideIn

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.get("/{request_id}", response_model=ContentRequestDetail)
def get_request_detail(request_id: str, user: dict = Depends(get_current_user)) -> ContentRequestDetail:
    return get_content_request_detail(request_id)


@router.patch("/{request_id}/sources/{source_id}", response_model=SourceOut)
def patch_source_status(
    request_id: str,
    source_id: str,
    body: SourceOverrideIn,
    user: dict = Depends(get_current_user),
) -> SourceOut:
    return override_source_status(request_id, source_id, body)
