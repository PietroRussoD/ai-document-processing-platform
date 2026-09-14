"""Shared infrastructure integration-test fixtures."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

POSTGRES_IMAGE = "postgres:18.6"


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer(
        image=POSTGRES_IMAGE,
        username="document_platform",
        password="integration-test-only",
        dbname="document_platform",
    ) as postgres:
        yield postgres.get_connection_url(driver="asyncpg")


@pytest.fixture(scope="session")
def migrated_postgres_url(postgres_url: str) -> Iterator[str]:
    configuration = Config("alembic.ini")
    with patch.dict(
        "os.environ",
        {"DOCUMENT_PLATFORM_DATABASE_URL": postgres_url},
    ):
        command.upgrade(configuration, "head")
        yield postgres_url
