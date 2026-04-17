from __future__ import annotations

from fastapi import Request

from app.core.settings import Settings
from app.graph import WorkflowEventStore
from app.services import ChatService, GenerationService, SessionService, SessionTaskManager


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def get_event_store(request: Request) -> WorkflowEventStore:
    return request.app.state.workflow_event_store


def get_task_manager(request: Request) -> SessionTaskManager:
    return request.app.state.session_task_manager
