from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import create_engine, create_sessionmaker, init_db
from app.routers import audit_logs, auth, items, organizations
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    engine = create_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Multi-Tenant Organization Manager", lifespan=lifespan)
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)

    app.include_router(auth.router)
    app.include_router(organizations.router)
    app.include_router(items.router)
    app.include_router(audit_logs.router)

    return app


app = create_app()
