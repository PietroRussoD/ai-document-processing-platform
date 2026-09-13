"""PostgreSQL integration-test fixtures."""

from collections.abc import Iterator

import pytest
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
