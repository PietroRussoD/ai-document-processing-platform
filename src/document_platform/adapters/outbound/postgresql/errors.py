"""PostgreSQL error classification helpers."""

from typing import cast

from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION_SQLSTATE = "23505"


def is_unique_violation(error: IntegrityError) -> bool:
    sqlstate = cast(str | None, getattr(error.orig, "sqlstate", None))
    return sqlstate == UNIQUE_VIOLATION_SQLSTATE


def unique_constraint_name(error: IntegrityError) -> str | None:
    driver_error = error.orig
    diagnostic = getattr(driver_error, "diag", None)
    constraint_name = cast(str | None, getattr(diagnostic, "constraint_name", None))
    if constraint_name is not None:
        return constraint_name

    cause = getattr(driver_error, "__cause__", None)
    return cast(str | None, getattr(cause, "constraint_name", None))
