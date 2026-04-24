import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def add_audit_log(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    message: str,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=action,
        message=message,
        meta=meta or {},
    )
    session.add(entry)
    await session.flush()
    return entry

