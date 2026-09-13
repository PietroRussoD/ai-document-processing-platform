"""Atomic application transaction contract."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from document_platform.application.ports.document_repository import DocumentRepository


class UnitOfWork(Protocol):
    @property
    def documents(self) -> DocumentRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


type UnitOfWorkFactory = Callable[[], UnitOfWork]
