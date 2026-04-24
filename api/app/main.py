from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat_doctor import router as chat_doctor_router
from app.api.chat_patient import router as chat_patient_router
from app.api.doctors import router as doctors_router
from app.api.patients import router as patients_router
from app.api.scribe import router as scribe_router
from app.api.translate import router as translate_router
from app.core.audit import AuditMiddleware
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Create all tables on startup (no-op if already exist)
    async with engine.begin() as conn:
        # Import models to register them with Base.metadata
        import app.db.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Dispose engine connections on shutdown
    await engine.dispose()


app = FastAPI(
    title="Decode Medical AI API",
    version="0.1.0",
    description="Phase 1 backend for the Decode medical AI application.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)

# All routers under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(patients_router, prefix="/api")
app.include_router(doctors_router, prefix="/api")
app.include_router(scribe_router, prefix="/api")
app.include_router(chat_patient_router, prefix="/api")
app.include_router(chat_doctor_router, prefix="/api")
app.include_router(translate_router, prefix="/api")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
