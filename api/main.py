"""FastAPI application entrypoint for the trading platform control plane.

Exposes read/monitoring endpoints plus explicit human-in-the-loop control
routes (mode transitions, kill switch). The API never *originates* trades on
its own — it surfaces state produced by the orchestration layer and lets an
operator supervise the system.

Run locally:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    account,
    governance,
    positions,
    research,
    risk,
    signals,
    strategies,
    system,
)
from api.schemas import HealthResponse
from config.logging_config import configure_logging, get_logger
from config.settings import get_settings
from core.system_state import get_system_state

logger = get_logger(__name__)

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    configure_logging()
    settings = get_settings()
    logger.info(
        "api.startup",
        app_name=settings.APP_NAME,
        env=settings.ENV,
        mode=get_system_state().get_mode().value,
        version=API_VERSION,
    )
    yield
    logger.info("api.shutdown")


def create_app() -> FastAPI:
    """Application factory — builds and configures the FastAPI instance."""
    settings = get_settings()
    app = FastAPI(
        title="Autonomous Adaptive Trading Intelligence Platform",
        description=(
            "Control plane for a modular, risk-first autonomous trading system. "
            "Defaults to PAPER mode; promotion PAPER -> SHADOW -> LIVE is gated."
        ),
        version=API_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Monitoring / read routers + human control routers.
    app.include_router(system.router)
    app.include_router(account.router)
    app.include_router(positions.router)
    app.include_router(strategies.router)
    app.include_router(signals.router)
    app.include_router(risk.router)
    app.include_router(research.router)
    app.include_router(governance.router)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        st = get_system_state()
        return HealthResponse(
            status="ok",
            mode=st.get_mode().value,
            trading_allowed=st.is_trading_allowed(),
            version=API_VERSION,
        )

    @app.get("/", tags=["health"])
    def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": API_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
