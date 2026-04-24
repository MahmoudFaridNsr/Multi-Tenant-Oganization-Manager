import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import add_audit_log
from app.db import get_session
from app.dependencies import get_current_user, require_org_role
from app.models import Item, Membership, Role, User
from app.schemas import ItemCreateRequest, ItemCreateResponse, ItemOut, ItemsPage


router = APIRouter(tags=["items"])


@router.post("/organizations/{org_id}/item", response_model=ItemCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    org_id: uuid.UUID,
    payload: ItemCreateRequest,
    session: AsyncSession = Depends(get_session),
    membership: Membership = Depends(require_org_role(Role.admin, Role.member)),
    current_user: User = Depends(get_current_user),
) -> ItemCreateResponse:
    if payload.org_id is not None and payload.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id mismatch")

    item = Item(org_id=org_id, created_by_user_id=current_user.id, item_details=payload.item_details)
    session.add(item)
    await session.flush()

    await add_audit_log(
        session,
        org_id=org_id,
        actor_user_id=current_user.id,
        action="item.created",
        message=f"Item created by {current_user.email}",
        meta={"item_id": str(item.id)},
    )
    await session.commit()
    return ItemCreateResponse(item_id=item.id)


@router.get("/organizations/{org_id}/item", response_model=ItemsPage)
async def list_items(
    org_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    membership: Membership = Depends(require_org_role(Role.admin, Role.member)),
    current_user: User = Depends(get_current_user),
) -> ItemsPage:
    stmt = select(Item).where(Item.org_id == org_id).order_by(Item.created_at.desc()).limit(limit).offset(offset)
    if membership.role != Role.admin:
        stmt = stmt.where(Item.created_by_user_id == current_user.id)

    items = (await session.scalars(stmt)).all()

    await add_audit_log(
        session,
        org_id=org_id,
        actor_user_id=current_user.id,
        action="items.listed",
        message=f"Items listed by {current_user.email}",
        meta={"limit": limit, "offset": offset},
    )
    await session.commit()

    return ItemsPage(
        items=[
            ItemOut(
                id=i.id,
                org_id=i.org_id,
                created_by_user_id=i.created_by_user_id,
                item_details=i.item_details,
                created_at=i.created_at,
            )
            for i in items
        ],
        limit=limit,
        offset=offset,
    )

