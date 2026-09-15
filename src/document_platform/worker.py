"""Standalone Temporal worker for document-processing workflows."""

import asyncio
import logging
from datetime import UTC, datetime

from temporalio.client import Client
from temporalio.worker import Worker

from document_platform.adapters.inbound.temporal import StartProcessingRunActivity
from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.application.commands import StartProcessingRunHandler
from document_platform.settings import Settings
from document_platform.workflows import ProcessBusinessDocumentWorkflow


async def run_worker(settings: Settings) -> None:
    database = create_database(settings)
    try:
        client = await Client.connect(
            settings.temporal_target_host,
            namespace=settings.temporal_namespace,
        )

        def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(database.sessions)

        activity = StartProcessingRunActivity(
            StartProcessingRunHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
            )
        )
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[ProcessBusinessDocumentWorkflow],
            activities=[activity.start_processing_run],
        )
        await worker.run()
    finally:
        await database.dispose()


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    try:
        asyncio.run(run_worker(settings))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
