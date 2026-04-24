import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrgCreateRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)


class OrgCreateResponse(BaseModel):
    org_id: uuid.UUID


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: Role


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    created_at: datetime


class UsersPage(BaseModel):
    items: list[UserOut]
    limit: int
    offset: int


class ItemCreateRequest(BaseModel):
    org_id: uuid.UUID | None = None
    item_details: dict[str, Any]


class ItemCreateResponse(BaseModel):
    item_id: uuid.UUID


class ItemOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    created_by_user_id: uuid.UUID
    item_details: dict[str, Any]
    created_at: datetime


class ItemsPage(BaseModel):
    items: list[ItemOut]
    limit: int
    offset: int


class AuditLogOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    message: str
    meta: dict[str, Any]
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    stream: bool = False

