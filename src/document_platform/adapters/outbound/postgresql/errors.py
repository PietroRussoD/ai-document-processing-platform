"""PostgreSQL error classification helpers."""

from typing import cast

from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION_SQLSTATE = "23505"


def is_unique_violation(error: IntegrityError) -> bool:
    sqlstate = cast(str | None, getattr(error.orig, "sqlstate", None))
    return sqlstate == UNIQUE_VIOLATION_SQLSTATE
