from fastapi import APIRouter, Depends

from app.services.draft_service import rewrite_draft
from auth.deps import get_current_user
from shared.models import DraftRewriteIn, RewriteAccepted

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.post("/{draft_id}/rewrite", response_model=RewriteAccepted)
def post_rewrite_draft(draft_id: str, body: DraftRewriteIn, user: dict = Depends(get_current_user)) -> dict:
    return rewrite_draft(draft_id, body.instructions)
