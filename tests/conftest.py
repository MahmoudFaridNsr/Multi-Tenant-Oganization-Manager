import os
import asyncio
from collections.abc import AsyncIterator, Iterator
from urllib.parse import urlparse, urlunparse

import pytest
from httpx import ASGITransport, AsyncClient
import asyncpg


def _to_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _to_asyncpg_driver_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _ensure_database_exists(database_url: str) -> None:
    parsed = urlparse(_to_asyncpg_driver_dsn(database_url))
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


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    local = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:123456@localhost:5432/org_manager_test",
    )
    asyncio.run(_ensure_database_exists(local))
    yield _to_asyncpg_url(local)


@pytest.fixture
async def client(database_url: str) -> AsyncIterator[AsyncClient]:
    os.environ["DATABASE_URL"] = database_url
    from app.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app
    from app.db import init_db

    app = create_app()
    await init_db(app.state.engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        await app.state.engine.dispose()
