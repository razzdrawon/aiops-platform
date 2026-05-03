"""
Shared test fixtures.

Integration tests use a real PostgreSQL database (TEST_DATABASE_URL).
Tables are assumed to exist (created by `alembic upgrade head` before running tests).
Each test gets a clean slate via TRUNCATE after it runs.
"""
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database import get_session
from app.api.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://aiops_user:aiops_pass@localhost:5432/aiops_test",
)


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Truncate all tables after each test for isolation."""
    yield
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE incidents RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """HTTP client wired to the test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    TestSessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with TestSessionFactory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()
