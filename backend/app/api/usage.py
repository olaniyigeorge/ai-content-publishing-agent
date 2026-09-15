from fastapi import APIRouter, Depends

from app.services.request_state_service import get_usage_summary
from auth.deps import get_current_user
from shared.models import UsageSummaryOut

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryOut)
def get_summary(user: dict = Depends(get_current_user)) -> UsageSummaryOut:
    return get_usage_summary()
