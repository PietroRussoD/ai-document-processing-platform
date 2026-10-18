"""Send lightweight Temporal heartbeats while isolated parser activities run."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from temporalio import activity


@asynccontextmanager
async def parser_activity_heartbeat() -> AsyncGenerator[None]:
    """Keep parser activities cancellable while their synchronous Job runs in a thread."""
    if not activity.in_activity():
        yield
        return

    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    try:
        yield
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(1)
        activity.heartbeat()
