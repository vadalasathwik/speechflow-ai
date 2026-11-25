from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def health_check() -> HealthResponse:
    """Return service liveness without external dependencies."""
    return HealthResponse(status="ok")
