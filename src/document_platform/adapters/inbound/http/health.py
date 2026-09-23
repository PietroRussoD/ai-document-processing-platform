"""Process-health HTTP endpoints."""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine


class LivenessResponse(BaseModel):
    status: Literal["UP"] = "UP"


class ReadinessResponse(BaseModel):
    status: Literal["UP", "DOWN"]
    database: Literal["UP", "DOWN"]


router = APIRouter(tags=["Health"])


@router.get(
    "/health/live",
    operation_id="getLiveness",
    summary="Check whether the API process is running",
)
async def get_liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/health/ready",
    operation_id="getReadiness",
    summary="Check whether the API can serve database-backed requests",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def get_readiness(request: Request) -> ReadinessResponse | JSONResponse:
    if await database_is_available(request.app.state.database.engine):
        return ReadinessResponse(status="UP", database="UP")
    return JSONResponse(
        status_code=503,
        content=ReadinessResponse(status="DOWN", database="DOWN").model_dump(),
    )


async def database_is_available(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
