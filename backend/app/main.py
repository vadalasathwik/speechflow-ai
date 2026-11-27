from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.session import router as session_router
from app.api.routes.transcription import router as transcription_router
from app.api.routes.transcriptions import router as transcriptions_router
from app.api.routes.realtime import router as realtime_router
from app.core.config import get_settings
from app.services.transcription import get_transcription_service


def create_application() -> FastAPI:
    settings = get_settings()
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.whisper_warmup_on_start:
            await run_in_threadpool(get_transcription_service().warm_up)
        yield

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(session_router, prefix=settings.api_v1_prefix)
    app.include_router(transcription_router, prefix=settings.api_v1_prefix)
    app.include_router(transcriptions_router, prefix=settings.api_v1_prefix)
    app.include_router(realtime_router)
    return app


app = create_application()
