import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import add_audit_log
from app.db import get_session
from app.dependencies import get_current_user, require_org_role
from app.models import Membership, Organization, Role, User
from app.schemas import InviteUserRequest, OrgCreateRequest, OrgCreateResponse, UserOut, UsersPage


router = APIRouter(tags=["organizations"])


@router.post("/organization", response_model=OrgCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OrgCreateResponse:
    org = Organization(org_name=payload.org_name)
    session.add(org)
    await session.flush()

    membership = Membership(user_id=current_user.id, org_id=org.id, role=Role.admin)
    session.add(membership)

    await add_audit_log(
        session,
        org_id=org.id,
        actor_user_id=current_user.id,
        action="organization.created",
        message=f"Organization created by {current_user.email}",
        meta={"org_id": str(org.id)},
    )

    await session.commit()
    return OrgCreateResponse(org_id=org.id)


@router.post("/organization/{org_id}/user", status_code=status.HTTP_201_CREATED)
async def add_user_to_organization(
    org_id: uuid.UUID,
    payload: InviteUserRequest,
    session: AsyncSession = Depends(get_session),
    membership: Membership = Depends(require_org_role(Role.admin)),
    current_user: User = Depends(get_current_user),
) -> dict:
    target = await session.scalar(select(User).where(User.email == payload.email))
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await session.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == target.id)
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already in organization")

    new_membership = Membership(user_id=target.id, org_id=org_id, role=payload.role)
    session.add(new_membership)
    await add_audit_log(
        session,
        org_id=org_id,
        actor_user_id=current_user.id,
        action="membership.created",
        message=f"User {target.email} added to organization by {current_user.email}",
        meta={"user_id": str(target.id), "role": payload.role.value},
    )
    await session.commit()
    return {"membership_id": new_membership.id}


@router.get("/organizations/{org_id}/users", response_model=UsersPage)
async def list_org_users(
    org_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Membership = Depends(require_org_role(Role.admin)),
) -> UsersPage:
    stmt = (
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.org_id == org_id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = (await session.scalars(stmt)).all()
    return UsersPage(
        items=[
            UserOut(id=u.id, email=u.email, full_name=u.full_name, created_at=u.created_at) for u in users
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/organizations/{org_id}/users/search", response_model=UsersPage)
async def search_org_users(
    org_id: uuid.UUID,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Membership = Depends(require_org_role(Role.admin)),
) -> UsersPage:
    ts_query = func.plainto_tsquery(q)
    vector = func.to_tsvector(func.coalesce(User.full_name, "") + " " + func.coalesce(User.email, ""))

    stmt = (
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.org_id == org_id)
        .where(vector.op("@@")(ts_query))
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = (await session.scalars(stmt)).all()
    return UsersPage(
        items=[
            UserOut(id=u.id, email=u.email, full_name=u.full_name, created_at=u.created_at) for u in users
        ],
        limit=limit,
        offset=offset,
    )
