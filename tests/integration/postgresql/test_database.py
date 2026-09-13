"""Real PostgreSQL connectivity tests."""

import pytest
from pydantic import PostgresDsn
from sqlalchemy import text

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_executes_a_query_with_an_owned_async_session(postgres_url: str) -> None:
    database = create_database(
        Settings(
            environment="test",
            database_url=PostgresDsn(postgres_url),
            database_pool_size=1,
            database_max_overflow=0,
        )
    )

    try:
        async with database.sessions() as session:
            result = await session.scalar(text("SELECT 1"))
    finally:
        await database.dispose()

    assert result == 1
