from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.health import router as health_router
from app.api.documents import router as documents_router
from app.api.verify import router as verify_router
from app.api.scheduler import router as scheduler_router
from app.services.news_scheduler import start_news_scheduler, stop_news_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background news ingestion scheduler on startup; stop on shutdown."""
    start_news_scheduler(interval_hours=6)
    yield
    stop_news_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=(
            "TruthTrace Backend — RAG-Powered Fake News Detection & Verification System\n\n"
            "Verify breaking news, auto-refresh the knowledge base, and fact-check claims "
            "with evidence from live RSS feeds, Google Fact Check, and NewsAPI."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(health_router, prefix=settings.API_V1_STR)
    app.include_router(documents_router, prefix=settings.API_V1_STR)
    app.include_router(verify_router, prefix=settings.API_V1_STR)
    app.include_router(scheduler_router, prefix=settings.API_V1_STR)

    @app.get("/")
    async def root():
        return {
            "message": "Welcome to TruthTrace Backend API",
            "docs": "/docs",
            "health": f"{settings.API_V1_STR}/health",
            "scheduler": f"{settings.API_V1_STR}/scheduler/status",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
