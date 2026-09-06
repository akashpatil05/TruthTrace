from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint returning application status.
    """
    return HealthResponse(
        status="ok",
        app=settings.PROJECT_NAME,
        version="0.1.0"
    )
