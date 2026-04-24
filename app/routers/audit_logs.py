import uuid
from collections import Counter
from datetime import date
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_current_user, require_org_role
from app.models import AuditLog, Membership, Role, User
from app.schemas import AskRequest, AuditLogOut
from app.settings import get_settings


router = APIRouter(tags=["audit"])

async def _answer_question(logs: list[AuditLog], question: str) -> str:
    q = question.lower().strip()
    today = date.today().isoformat()

    if "how many" in q and "user" in q and "today" in q:
        invited_user_ids = {
            str(log.meta.get("user_id"))
            for log in logs
            if log.action == "membership.created" and "user_id" in log.meta
        }
        invited_user_ids.discard("None")
        return f"Today ({today}) {len(invited_user_ids)} user(s) were added to the organization."

    counts = Counter(log.action for log in logs)
    top = ", ".join(f"{action}={count}" for action, count in counts.most_common(10)) or "no events"
    return f"Today ({today}) activity summary: {top}."


async def _stream_text(text: str, chunk_size: int = 32):
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]

def _logs_to_text(logs: list[AuditLog]) -> str:
    lines: list[str] = []
    for log in logs:
        ts = log.created_at.isoformat() if log.created_at else ""
        lines.append(f"{ts} | {log.action} | {log.message} | meta={log.meta}")
    return "\n".join(lines)


async def _gemini_answer(*, question: str, logs: list[AuditLog]) -> str | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None

    logs_text = _logs_to_text(logs)
    prompt = (
        "You are an assistant helping an organization admin understand what happened today.\n"
        "Answer based ONLY on the audit logs provided. If the answer is not in the logs, say you can't tell.\n\n"
        f"Question: {question}\n\n"
        "Audit logs:\n"
        f"{logs_text}"
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, params={"key": settings.gemini_api_key}, json=payload)
        if resp.status_code != 200:
            return None
        data = resp.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


@router.get("/organizations/{org_id}/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    org_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Membership = Depends(require_org_role(Role.admin)),
) -> list[AuditLogOut]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = (await session.scalars(stmt)).all()
    return [
        AuditLogOut(
            id=l.id,
            org_id=l.org_id,
            actor_user_id=l.actor_user_id,
            action=l.action,
            message=l.message,
            meta=l.meta,
            created_at=l.created_at,
        )
        for l in logs
    ]


@router.post("/organizations/{org_id}/audit-logs/ask", response_model=None)
async def ask_audit_logs(
    org_id: uuid.UUID,
    payload: AskRequest,
    session: AsyncSession = Depends(get_session),
    _: Membership = Depends(require_org_role(Role.admin)),
    __: User = Depends(get_current_user),
) -> object:
    now = datetime.now(timezone.utc)
    day_start = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)

    stmt = select(AuditLog).where(AuditLog.org_id == org_id, AuditLog.created_at >= day_start).order_by(
        AuditLog.created_at.asc()
    )
    logs = (await session.scalars(stmt)).all()

    answer = await _gemini_answer(question=payload.question, logs=logs)
    if not answer:
        answer = await _answer_question(logs, payload.question)

    if payload.stream:
        return StreamingResponse(_stream_text(answer), media_type="text/plain")

    return {"answer": answer}
