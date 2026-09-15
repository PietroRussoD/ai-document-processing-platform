"""Standalone process that hands durable workflow requests to Temporal."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from temporalio.client import Client

from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.temporal import TemporalWorkflowStarter
from document_platform.application.commands import (
    ClaimWorkflowStartRequests,
    ClaimWorkflowStartRequestsHandler,
    DispatchWorkflowStartRequestsHandler,
    WorkflowStartDispatchResult,
)
from document_platform.settings import Settings

logger = logging.getLogger(__name__)

type DispatchWorkflowStartRequests = Callable[
    [ClaimWorkflowStartRequests],
    Awaitable[WorkflowStartDispatchResult],
]


async def run_dispatch_cycle(
    dispatch_workflow_start_requests: DispatchWorkflowStartRequests,
    settings: Settings,
) -> WorkflowStartDispatchResult:
    return await dispatch_workflow_start_requests(
        ClaimWorkflowStartRequests(
            owner=settings.dispatcher_owner,
            limit=settings.dispatcher_batch_size,
            lease_duration=timedelta(seconds=settings.dispatcher_lease_seconds),
        )
    )


async def run_dispatcher(settings: Settings) -> None:
    database = create_database(settings)
    try:
        client = await Client.connect(
            settings.temporal_target_host,
            namespace=settings.temporal_namespace,
        )

        def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(database.sessions)

        claim = ClaimWorkflowStartRequestsHandler(
            unit_of_work_factory=unit_of_work_factory,
            clock=lambda: datetime.now(UTC),
            id_generator=uuid4,
        )
        dispatch = DispatchWorkflowStartRequestsHandler(
            claim_workflow_start_requests=claim,
            workflow_starter=TemporalWorkflowStarter(
                client,
                task_queue=settings.temporal_task_queue,
            ),
            unit_of_work_factory=unit_of_work_factory,
            clock=lambda: datetime.now(UTC),
        )
        while True:
            result = await run_dispatch_cycle(dispatch, settings)
            _log_dispatch_result(result)
            await asyncio.sleep(settings.dispatcher_poll_seconds)
    finally:
        await database.dispose()


def _log_dispatch_result(result: WorkflowStartDispatchResult) -> None:
    if result.deferred_count:
        logger.warning(
            "workflow-start dispatch deferred claimed=%s dispatched=%s deferred=%s",
            result.claimed_count,
            result.dispatched_count,
            result.deferred_count,
        )
    elif result.dispatched_count:
        logger.info(
            "workflow-start dispatch completed claimed=%s dispatched=%s",
            result.claimed_count,
            result.dispatched_count,
        )


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    try:
        asyncio.run(run_dispatcher(settings))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
