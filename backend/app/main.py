from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents import build_agent_runtime
from app.api.routes.health import router as health_router
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.knowledge import StyleKnowledgeProvider
from app.middlewares.error_handler import register_error_handlers
from app.middlewares.request_context import RequestContextMiddleware
from app.prompts import PromptRegistry, PromptRenderer
from app.storage import CleanupService, SessionStore, TempFileManager


logger = logging.getLogger(__name__)


async def cleanup_loop(cleanup_service: CleanupService, interval_seconds: int) -> None:
    while True:
        expired_report = cleanup_service.purge_expired_sessions()
        if expired_report.removed_sessions or expired_report.failed_targets:
            logger.info(
                "Expired session cleanup finished: removed_sessions=%s removed_directories=%s failed_targets=%s",
                len(expired_report.removed_sessions),
                len(expired_report.removed_directories),
                len(expired_report.failed_targets),
            )

        orphan_report = cleanup_service.cleanup_orphaned_directories()
        if orphan_report.removed_directories or orphan_report.failed_targets:
            logger.info(
                "Orphan temp directory cleanup finished: removed_directories=%s failed_targets=%s",
                len(orphan_report.removed_directories),
                len(orphan_report.failed_targets),
            )

        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    session_store = SessionStore(ttl_seconds=settings.session_ttl_seconds)
    temp_file_manager = TempFileManager(settings.temp_dir)
    cleanup_service = CleanupService(session_store=session_store, temp_file_manager=temp_file_manager)
    prompt_registry = PromptRegistry()
    prompt_renderer = PromptRenderer()
    style_knowledge_provider = StyleKnowledgeProvider()
    agent_runtime = build_agent_runtime(
        settings,
        prompt_registry=prompt_registry,
        prompt_renderer=prompt_renderer,
        style_knowledge_provider=style_knowledge_provider,
    )

    app.state.session_store = session_store
    app.state.temp_file_manager = temp_file_manager
    app.state.cleanup_service = cleanup_service
    app.state.prompt_registry = prompt_registry
    app.state.prompt_renderer = prompt_renderer
    app.state.style_knowledge_provider = style_knowledge_provider
    app.state.agent_runtime = agent_runtime

    startup_cleanup_report = cleanup_service.cleanup_orphaned_directories()
    if startup_cleanup_report.removed_directories or startup_cleanup_report.failed_targets:
        logger.info(
            "Startup temp cleanup finished: removed_directories=%s failed_targets=%s",
            len(startup_cleanup_report.removed_directories),
            len(startup_cleanup_report.failed_targets),
        )

    cleanup_task = asyncio.create_task(
        cleanup_loop(cleanup_service, settings.session_cleanup_interval_seconds)
    )
    app.state.cleanup_task = cleanup_task

    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="DrawAgent Backend",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    register_error_handlers(app)

    return app


app = create_app()
