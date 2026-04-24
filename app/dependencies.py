import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Membership, Role, User
from app.security import decode_access_token
from app.settings import get_settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    settings = get_settings()
    try:
        payload = decode_access_token(settings, token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sub = payload.get("sub")
    try:
        user_id = uuid.UUID(str(sub))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_membership(
    org_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> Membership:
    stmt = select(Membership).where(Membership.org_id == org_id, Membership.user_id == current_user.id)
    membership = await session.scalar(stmt)
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of organization")
    return membership


def require_org_role(*allowed_roles: Role) -> Callable:
    async def _dependency(
        org_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> Membership:
        membership = await get_membership(org_id=org_id, current_user=current_user, session=session)
        if allowed_roles and membership.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return membership

    return _dependency
