from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class RequestCodeRequest(BaseModel):
    email: EmailStr


class RequestCodeResponse(BaseModel):
    message: str = "if this email is eligible, a code has been sent"


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyCodeResponse(BaseModel):
    message: str = "logged in"


class MeResponse(BaseModel):
    id: UUID
    email: str
    last_login_at: datetime | None


class AccessRuleIn(BaseModel):
    type: str
    value: str
    enabled: bool = True
    expires_at: datetime | None = None


class AccessRuleOut(AccessRuleIn):
    id: UUID
    created_at: datetime
