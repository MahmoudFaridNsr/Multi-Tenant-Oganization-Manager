import asyncio
from urllib.parse import urlparse, urlunparse

import asyncpg
from sqlalchemy import select

from app.audit import add_audit_log
from app.db import create_engine, create_sessionmaker, init_db
from app.models import Item, Membership, Organization, Role, User
from app.security import hash_password
from app.settings import get_settings


def _asyncpg_driver_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _ensure_database_exists(database_url: str) -> None:
    parsed = urlparse(_asyncpg_driver_dsn(database_url))
    db_name = parsed.path.lstrip("/")
    admin_parsed = parsed._replace(path="/postgres")
    admin_dsn = urlunparse(admin_parsed)

    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("select 1 from pg_database where datname = $1", db_name)
        if not exists:
            await conn.execute(f'create database "{db_name}"')
    finally:
        await conn.close()


async def seed() -> None:
    settings = get_settings()
    await _ensure_database_exists(settings.database_url)

    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    await init_db(engine)

    async with sessionmaker() as session:
        password = "StrongPassword123"

        admin_email = "admin@example.com"
        member_email = "member@example.com"

        admin_user = await session.scalar(select(User).where(User.email == admin_email))
        if not admin_user:
            admin_user = User(
                email=admin_email,
                full_name="Admin User",
                password_hash=hash_password(settings, password),
            )
            session.add(admin_user)
            await session.flush()

        member_user = await session.scalar(select(User).where(User.email == member_email))
        if not member_user:
            member_user = User(
                email=member_email,
                full_name="Member User",
                password_hash=hash_password(settings, password),
            )
            session.add(member_user)
            await session.flush()

        org = await session.scalar(select(Organization).where(Organization.org_name == "Electro Pi"))
        if not org:
            org = Organization(org_name="Electro Pi")
            session.add(org)
            await session.flush()

            session.add(Membership(user_id=admin_user.id, org_id=org.id, role=Role.admin))
            await add_audit_log(
                session,
                org_id=org.id,
                actor_user_id=admin_user.id,
                action="organization.created",
                message=f"Organization created by {admin_user.email}",
                meta={"org_id": str(org.id)},
            )

        admin_membership = await session.scalar(
            select(Membership).where(Membership.user_id == admin_user.id, Membership.org_id == org.id)
        )
        if not admin_membership:
            session.add(Membership(user_id=admin_user.id, org_id=org.id, role=Role.admin))

        member_membership = await session.scalar(
            select(Membership).where(Membership.user_id == member_user.id, Membership.org_id == org.id)
        )
        if not member_membership:
            session.add(Membership(user_id=member_user.id, org_id=org.id, role=Role.member))
            await add_audit_log(
                session,
                org_id=org.id,
                actor_user_id=admin_user.id,
                action="membership.created",
                message=f"User {member_user.email} added to organization by {admin_user.email}",
                meta={"user_id": str(member_user.id), "role": Role.member.value},
            )

        existing_item = await session.scalar(
            select(Item).where(Item.org_id == org.id, Item.created_by_user_id == member_user.id)
        )
        if not existing_item:
            item1 = Item(
                org_id=org.id,
                created_by_user_id=member_user.id,
                item_details={"title": "First item", "note": "created by member"},
            )
            session.add(item1)
            await session.flush()
            await add_audit_log(
                session,
                org_id=org.id,
                actor_user_id=member_user.id,
                action="item.created",
                message=f"Item created by {member_user.email}",
                meta={"item_id": str(item1.id)},
            )

            item2 = Item(
                org_id=org.id,
                created_by_user_id=admin_user.id,
                item_details={"title": "Admin item", "note": "created by admin"},
            )
            session.add(item2)
            await session.flush()
            await add_audit_log(
                session,
                org_id=org.id,
                actor_user_id=admin_user.id,
                action="item.created",
                message=f"Item created by {admin_user.email}",
                meta={"item_id": str(item2.id)},
            )

        await session.commit()

    await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

