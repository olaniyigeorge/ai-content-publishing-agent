from fastapi import APIRouter, Depends

from app.services.review_service import submit_review
from auth.deps import get_current_user
from shared.models import HumanReviewIn, HumanReviewOut

router = APIRouter(prefix="/api/requests", tags=["reviews"])


@router.post("/{request_id}/review", response_model=HumanReviewOut)
def post_review(request_id: str, body: HumanReviewIn, user: dict = Depends(get_current_user)) -> HumanReviewOut:
    return submit_review(request_id, body, reviewer_user_id=str(user["id"]))
