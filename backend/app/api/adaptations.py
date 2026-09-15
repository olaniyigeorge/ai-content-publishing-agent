from fastapi import APIRouter, Depends

from app.services.adaptation_service import rewrite_channel_adaptation
from auth.deps import get_current_user
from shared.models import ChannelAdaptationRewriteIn, RewriteAccepted

router = APIRouter(prefix="/api/channel-adaptations", tags=["channel-adaptations"])


@router.post("/{adaptation_id}/rewrite", response_model=RewriteAccepted)
def post_rewrite_adaptation(
    adaptation_id: str, body: ChannelAdaptationRewriteIn, user: dict = Depends(get_current_user)
) -> dict:
    return rewrite_channel_adaptation(adaptation_id, body.instructions)
