"""Migration-set consistency tests."""

from unittest.mock import patch

from alembic import command
from alembic.config import Config


def test_migrations_match_sqlalchemy_metadata(migrated_postgres_url: str) -> None:
    configuration = Config("alembic.ini")
    with patch.dict(
        "os.environ",
        {"DOCUMENT_PLATFORM_DATABASE_URL": migrated_postgres_url},
    ):
        command.check(configuration)
