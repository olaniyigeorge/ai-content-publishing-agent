from fastapi import APIRouter, Depends

from app.services.draft_service import manual_edit_draft, rewrite_draft
from auth.deps import get_current_user
from shared.models import ArticleDraftOut, DraftManualEditIn, DraftRewriteIn, RewriteAccepted

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.post("/{draft_id}/rewrite", response_model=RewriteAccepted)
def post_rewrite_draft(draft_id: str, body: DraftRewriteIn, user: dict = Depends(get_current_user)) -> dict:
    return rewrite_draft(draft_id, body.instructions)


@router.put("/{draft_id}", response_model=ArticleDraftOut)
def put_edit_draft(draft_id: str, body: DraftManualEditIn, user: dict = Depends(get_current_user)) -> dict:
    return manual_edit_draft(draft_id, body.title, body.body_markdown)
