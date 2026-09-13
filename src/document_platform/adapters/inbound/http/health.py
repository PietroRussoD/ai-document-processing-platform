"""Process-health HTTP endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["UP"] = "UP"


router = APIRouter(tags=["Health"])


@router.get(
    "/health/live",
    operation_id="getLiveness",
    summary="Check whether the API process is running",
)
async def get_liveness() -> LivenessResponse:
    return LivenessResponse()
