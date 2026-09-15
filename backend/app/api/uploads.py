from fastapi import APIRouter, Depends, UploadFile

from app.services.upload_service import upload_intake_asset
from auth.deps import get_current_user

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("")
async def post_upload(file: UploadFile, user: dict = Depends(get_current_user)) -> dict:
    data = await file.read()
    return upload_intake_asset(filename=file.filename or "upload", content_type=file.content_type, data=data)
