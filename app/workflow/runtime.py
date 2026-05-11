from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.checkpoint_store import CheckpointStore
from app.core.artifact_store import ArtifactStore
from app.core.config import AppConfig
from app.core.logging import debug_event
from app.core.models import ReviewVerdict
from app.core.run_events import RunEventStore
from app.core.state import WorkflowState
from app.agents.registry import AgentRegistry
from app.llm.openai_client import OpenAICompatibleClient
from app.prompts.repository import PromptRepository
from app.skills.repository import SkillRepository
from app.skills.validator import validate_skill_plan
from app.tools.review_tool import ReviewToolClient
from app.workflow.graph import DualNodeWorkflowGraph
from app.workflow.task_executor import VirtualTaskExecutor


@dataclass
class WorkflowResult:
    session_id: str
    stage: str
    checkpoint_id: str
    payload_final: dict[str, Any]
    workflow_state: dict[str, Any]
    document_context_summary: dict[str, Any]
    selected_skill: str


class DrawAgentRuntime:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.config = AppConfig.load(root_dir)
        self.prompt_repository = PromptRepository(root_dir, self.config.prompt_manifest_path)
        self.agent_registry = AgentRegistry.from_root(root_dir)
        self.skill_repository = SkillRepository(root_dir)
        controller_llm = self.config.llm_role("controller")
        self.controller_client = OpenAICompatibleClient(
            base_url=controller_llm.base_url,
            api_key=controller_llm.api_key,
            api_mode=controller_llm.api_mode,
        )
        self.llm_client = self.controller_client
        self.image_client = OpenAICompatibleClient(
            base_url=self.config.image_base_url,
            api_key=self.config.image_api_key,
            image_api_mode=self.config.image_api_mode,
        )
        self.review_tool = ReviewToolClient(self.config)
        self.checkpoint_store = CheckpointStore(self.config.artifact_dir / "checkpoints")
        self.artifact_store = ArtifactStore(self.config.artifact_dir / "artifacts")
        self.event_store = RunEventStore(self.config.artifact_dir / "runs")
        self.task_executor = VirtualTaskExecutor(
            max_workers=self.config.max_concurrent_virtual_tasks,
            event_store=self.event_store,
        )
        self.session_state_dir = self.config.artifact_dir / "sessions"
        self.session_state_dir.mkdir(parents=True, exist_ok=True)
        self._stop_requests: set[str] = set()
        self.graph_runner = DualNodeWorkflowGraph(self)

    def close(self) -> None:
        self.review_tool.close()

    def describe_agents(self) -> list[dict[str, Any]]:
        controller_llm = self.config.llm_role("controller")
        reviewer_llm = self.config.llm_role("reviewer")
        agents = [
            {
                "name": "controller",
                "model": controller_llm.model,
                "role": "controller",
                "mode": "tool_call",
                "request_api_mode": controller_llm.api_mode,
            }
        ]
        for profile in self.agent_registry.describe():
            role_llm = self.config.llm_role(str(profile.get("model_role") or "worker_default"))
            agents.append(
                {
                    "name": profile["name"],
                    "model": role_llm.model,
                    "role": profile.get("default_role", "generic"),
                    "mode": "mcp_virtual_agent",
                    "request_api_mode": role_llm.api_mode,
                    "prompt_name": profile.get("prompt_name", ""),
                    "output_contract": profile.get("output_contract", ""),
                    "allowed_input_refs": profile.get("allowed_input_refs", []),
                }
            )
        agents.append(
            {
                "name": "reviewer",
                "model": reviewer_llm.model,
                "role": "reviewer",
                "mode": "mcp_tool_call",
                "request_api_mode": reviewer_llm.api_mode,
            }
        )
        return agents

    def describe_skills(self) -> list[dict[str, Any]]:
        return self.skill_repository.describe()

    def describe_workflow(self) -> dict[str, Any]:
        return {
            "name": "drawAgent-v2",
            "type": "dual-node-stategraph",
            "nodes": ["controller_node", "virtual_worker_node"],
            "states": [
                "initial",
                "skill_selected",
                "logic_extraction",
                "style_extraction",
                "visual_mapping",
                "summarization",
                "awaiting_user_confirmation",
                "image_generation_requested",
                "image_generation_completed",
                "stopped",
                "review_failed",
            ],
            "messages": [
                "positive_check",
                "negative_review",
                "fatal_review",
                "warning_release",
                "image_generated",
                "clarification_needed",
            ],
            "stages": [
                "logic_extraction",
                "style_extraction",
                "visual_mapping",
                "summarization",
                "image_generation",
            ],
            "routes": {
                "start_new_task": {
                    "stages": [
                        {"stage": "logic_extraction", "actor": "virtual_worker", "depends_on": []},
                        {"stage": "style_extraction", "actor": "virtual_worker", "depends_on": []},
                        {"stage": "visual_mapping", "actor": "virtual_worker", "depends_on": ["logic_extraction", "style_extraction"]},
                        {"stage": "summarization", "actor": "virtual_worker", "depends_on": ["visual_mapping"]},
                        {"stage": "image_generation", "actor": "virtual_worker", "trigger": "user_confirm"},
                    ]
                }
            },
        }

    def _document_context_summary(self, document_context: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_count": document_context.get("file_count", 0),
            "parsed_file_count": document_context.get("parsed_file_count", 0),
            "warnings": document_context.get("warnings", []),
            "combined_excerpt": document_context.get("combined_excerpt", ""),
            "files": [
                {
                    "name": item.get("name"),
                    "extension": item.get("extension"),
                    "status": item.get("status"),
                    "parser": item.get("parser"),
                    "char_count": item.get("char_count"),
                }
                for item in document_context.get("files", [])
            ],
        }

    def build_initial_state(
        self,
        *,
        session_id: str,
        user_input: str,
        document_context: dict[str, Any],
    ) -> WorkflowState:
        return {
            "session_id": session_id,
            "user_input": user_input,
            "document_context": document_context,
            "document_context_summary": self._document_context_summary(document_context),
            "primary_discipline": "",
            "conference_name": "",
            "user_preferences": "",
            "missing_clarification_fields": [],
            "selected_skill": "",
            "detected_intent": "",
            "target_skill": "",
            "routing_reason": "",
            "skill_plan": [],
            "orchestration_plan": {},
            "awaiting_orchestration_confirmation": False,
            "orchestration_confirmed": False,
            "messages": [],
            "pending_tasks": [],
            "active_task": None,
            "active_tasks": [],
            "active_task_run_ids": [],
            "completed_tasks": [],
            "artifacts": {
                "stage_outputs": {},
                "artifact_refs": {},
                "payload_logic": {"key": "logician", "value": ""},
                "payload_style": {"key": "style_designer", "value": ""},
                "payload_mapper": {"key": "visual_mapper", "value": ""},
                "payload_final": {"key": "summarizer", "value": ""},
                "image_result": {"key": "image_generator", "value": {}},
            },
            "review_history": [],
            "warnings": [],
            "stage": "initial",
            "next_hop": "end",
            "awaiting_user_confirmation": False,
            "stop_requested": False,
            "released_with_warnings": False,
            "prompt_checkpoint_id": "",
            "prompt_checkpoint_path": "",
            "image_attempt_id": "",
            "final_response": {},
            "error": "",
        }

    def clear_stop_request(self, session_id: str) -> None:
        self._stop_requests.discard(session_id)

    def request_stop(self, session_id: str) -> bool:
        if not session_id:
            return False
        self._stop_requests.add(session_id)
        cancelled_tasks = self.task_executor.cancel_session(session_id)
        self.record_event("workflow.stop_requested", session_id=session_id, cancelled_tasks=cancelled_tasks)
        debug_event("stop_requested", session_id=session_id, cancelled_tasks=cancelled_tasks)
        return True

    def request_stop_for_checkpoint(self, checkpoint_id: str) -> bool:
        if not checkpoint_id:
            return False
        checkpoint = self.checkpoint_store.load(checkpoint_id)
        session_id = str(checkpoint.get("workflow_state", {}).get("session_id") or "")
        return self.request_stop(session_id)

    def is_stop_requested(self, session_id: str) -> bool:
        return bool(session_id and session_id in self._stop_requests)

    def _session_state_path(self, session_id: str) -> Path:
        return self.session_state_dir / f"{session_id}.json"

    def load_session_state(self, session_id: str) -> WorkflowState | None:
        path = self._session_state_path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_session_state(self, state: WorkflowState) -> None:
        session_id = str(state.get("session_id") or "")
        if not session_id:
            return
        self._session_state_path(session_id).write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def record_event(self, event_type: str, *, session_id: str = "", **payload: Any) -> dict[str, Any]:
        return self.event_store.append(event_type, session_id=session_id, **payload)

    def list_task_records(self, session_id: str) -> list[dict[str, Any]]:
        return self.task_executor.list(session_id=session_id)

    def read_run_events(self, session_id: str) -> list[dict[str, Any]]:
        return self.event_store.read(session_id)

    def _build_progressive_initial_state(
        self,
        *,
        session_id: str,
        user_input: str,
        document_context: dict[str, Any],
    ) -> WorkflowState:
        state = self.build_initial_state(
            session_id=session_id,
            user_input=user_input,
            document_context=document_context,
        )
        previous = self.load_session_state(session_id)
        if not previous:
            return state

        previous_document_context = previous.get("document_context", {}) or {}
        if not document_context.get("file_count") and previous_document_context.get("file_count"):
            state["document_context"] = previous_document_context
            state["document_context_summary"] = self._document_context_summary(previous_document_context)

        for key in ("primary_discipline", "conference_name", "user_preferences"):
            if previous.get(key):
                state[key] = str(previous.get(key) or "")

        state["artifacts"] = previous.get("artifacts", state["artifacts"])
        state["review_history"] = previous.get("review_history", [])
        state["warnings"] = previous.get("warnings", [])
        return state

    def start_prompt_pipeline(
        self,
        *,
        session_id: str,
        user_input: str,
        document_context: dict[str, Any],
    ) -> WorkflowResult:
        self.record_event(
            "workflow.started",
            session_id=session_id,
            has_document=bool(document_context.get("file_count") or document_context.get("combined_text")),
            user_input_chars=len(user_input or ""),
        )
        final_state = self.graph_runner.run(
            self._build_progressive_initial_state(
                session_id=session_id,
                user_input=user_input,
                document_context=document_context,
            )
        )
        self.save_session_state(final_state)
        self.record_event(
            "workflow.finished",
            session_id=session_id,
            stage=final_state.get("stage", ""),
            selected_skill=final_state.get("selected_skill", ""),
        )
        payload_final = final_state.get("artifacts", {}).get("payload_final", {})
        return WorkflowResult(
            session_id=session_id,
            stage=str(final_state.get("stage") or ""),
            checkpoint_id=str(final_state.get("prompt_checkpoint_id") or ""),
            payload_final=payload_final,
            workflow_state=final_state,
            document_context_summary=final_state.get("document_context_summary", {}),
            selected_skill=str(final_state.get("selected_skill") or ""),
        )

    def confirm_orchestration(self, session_id: str) -> dict[str, Any]:
        state = self.load_session_state(session_id)
        if not state:
            raise FileNotFoundError(session_id)
        if state.get("stage") != "awaiting_orchestration_confirmation":
            raise ValueError("session is not awaiting orchestration confirmation")
        validation = validate_skill_plan(list(state.get("skill_plan", []) or []))
        if not validation.get("ok", False):
            raise ValueError("session orchestration plan is invalid")
        self.clear_stop_request(str(state.get("session_id") or ""))
        state["awaiting_orchestration_confirmation"] = False
        state["orchestration_confirmed"] = True
        state["stage"] = "skill_selected"
        state["next_hop"] = "controller"
        debug_event(
            "orchestration_confirmed",
            session_id=session_id,
            selected_skill=state.get("selected_skill", ""),
        )
        self.record_event(
            "orchestration.confirmed",
            session_id=session_id,
            selected_skill=state.get("selected_skill", ""),
        )
        final_state = self.graph_runner.run(state)
        self.save_session_state(final_state)
        return {
            "session_id": final_state.get("session_id"),
            "stage": final_state.get("stage"),
            "checkpoint_id": final_state.get("prompt_checkpoint_id", ""),
            "payload_final": final_state.get("artifacts", {}).get("payload_final", {}),
            "workflow_state": final_state,
            "document_context_summary": final_state.get("document_context_summary", {}),
            "selected_skill": final_state.get("selected_skill", ""),
            "confirm_required": bool(final_state.get("prompt_checkpoint_id")),
        }

    def confirm_image_generation(self, checkpoint_id: str) -> dict[str, Any]:
        checkpoint = self.checkpoint_store.load(checkpoint_id)
        state = checkpoint["workflow_state"]
        self.clear_stop_request(str(state.get("session_id") or ""))
        image_attempt_id = str(uuid4())
        state["awaiting_user_confirmation"] = False
        state["stage"] = "image_generation_requested"
        state["next_hop"] = "controller"
        state["prompt_checkpoint_id"] = checkpoint_id
        state["image_attempt_id"] = image_attempt_id
        debug_event(
            "image_attempt_started",
            checkpoint_id=checkpoint_id,
            session_id=state.get("session_id", ""),
            image_attempt_id=image_attempt_id,
        )
        self.record_event(
            "image.started",
            session_id=str(state.get("session_id") or ""),
            checkpoint_id=checkpoint_id,
            image_attempt_id=image_attempt_id,
        )
        final_state = self.graph_runner.run(state)
        self.save_session_state(final_state)
        image_result = final_state.get("artifacts", {}).get("image_result", {}).get("value", {})
        public_image_url = (
            image_result.get("public_url")
            or image_result.get("image_url")
            or image_result.get("local_path")
            or ""
        )
        if not public_image_url and final_state.get("stage") == "image_generation_completed":
            final_state["stage"] = "image_generation_failed"
        debug_event(
            "image_attempt_finished",
            checkpoint_id=checkpoint_id,
            session_id=final_state.get("session_id", ""),
            image_attempt_id=image_result.get("image_attempt_id") or image_attempt_id,
            stage=final_state.get("stage", ""),
            provider_request_id=image_result.get("provider_request_id", ""),
            provider_duration_ms=image_result.get("provider_duration_ms", 0),
            public_image_url=public_image_url,
            local_path=image_result.get("local_path", ""),
        )
        self.record_event(
            "image.finished",
            session_id=str(final_state.get("session_id") or ""),
            checkpoint_id=checkpoint_id,
            image_attempt_id=image_result.get("image_attempt_id") or image_attempt_id,
            stage=final_state.get("stage", ""),
            public_image_url=public_image_url,
        )
        return {
            "session_id": final_state.get("session_id"),
            "stage": (
                "image_generation_failed"
                if not public_image_url and final_state.get("stage") == "image_generation_completed"
                else final_state.get("stage")
            ),
            "checkpoint_id": final_state.get("prompt_checkpoint_id"),
            "payload_final": final_state.get("artifacts", {}).get("payload_final", {}),
            "image_result": final_state.get("artifacts", {}).get("image_result", {}),
            "image_attempt_id": image_result.get("image_attempt_id") or image_attempt_id,
            "image_url": public_image_url,
            "revised_prompt": image_result.get("revised_prompt") or "",
            "provider_request": {
                "request": "image_generation",
                "model": self.config.image_model,
                "request_api_mode": self.config.image_api_mode,
                "image_attempt_id": image_result.get("image_attempt_id") or image_attempt_id,
                "provider_request_id": image_result.get("provider_request_id") or "",
                "provider_request_path": image_result.get("provider_request_path") or "",
                "provider_duration_ms": image_result.get("provider_duration_ms") or 0,
            },
            "message": (
                "图片生成完成。"
                if final_state.get("stage") == "image_generation_completed"
                else "图片生成流程已结束。"
            ),
            "workflow_state": final_state,
        }

    def revise_prompt_checkpoint(self, checkpoint_id: str, revision_instruction: str) -> dict[str, Any]:
        checkpoint = self.checkpoint_store.load(checkpoint_id)
        state = checkpoint["workflow_state"]
        raw_value = state.get("artifacts", {}).get("payload_final", {}).get("value", "")
        if isinstance(raw_value, dict):
            current_prompt = str(raw_value.get("english_prompt") or raw_value.get("value") or "")
        else:
            current_prompt = str(raw_value or "")
        revised_prompt = (
            f"{current_prompt.strip()}\n\n"
            "User revision requirement:\n"
            f"{revision_instruction.strip()}\n\n"
            "Apply the revision while preserving source fidelity, scientific accuracy, and the reviewed upstream logic."
        ).strip()
        state.setdefault("artifacts", {})["payload_final"] = {
            "key": "summarizer",
            "value": revised_prompt,
        }
        state["awaiting_user_confirmation"] = True
        state["stage"] = "awaiting_user_confirmation"
        state["final_response"] = {
            "chinese_explanation": "已根据你的补充要求修订 Prompt，请确认后开始生图。",
            "review_status": "user_revised",
            "review_approved": False,
            "review_warning": "该版本包含用户后续修订要求，建议确认后再出图。",
            "latest_review_feedback": state.get("review_history", [])[-1] if state.get("review_history") else {},
        }
        new_checkpoint_id, checkpoint_path = self.save_prompt_checkpoint(state)
        state["prompt_checkpoint_id"] = new_checkpoint_id
        state["prompt_checkpoint_path"] = checkpoint_path
        self.save_session_state(state)
        return {
            "session_id": state.get("session_id"),
            "stage": state.get("stage"),
            "checkpoint_id": new_checkpoint_id,
            "payload_final": state.get("artifacts", {}).get("payload_final", {}),
            "workflow_state": state,
            "document_context_summary": state.get("document_context_summary", {}),
            "selected_skill": state.get("selected_skill", ""),
            "confirm_required": True,
        }

    def save_prompt_checkpoint(self, state: WorkflowState) -> tuple[str, str]:
        checkpoint_id = f"{state['session_id']}-{uuid4()}-prompt-ready"
        payload = {
            "checkpoint_id": checkpoint_id,
            "workflow_state": state,
            "payload_final": state.get("artifacts", {}).get("payload_final", {}),
        }
        path = self.checkpoint_store.save(checkpoint_id, payload)
        debug_event("checkpoint_saved", checkpoint_id=checkpoint_id, checkpoint_path=path)
        return checkpoint_id, path

    def run_review(
        self,
        *,
        review_phase: str,
        target_goal: str,
        task_type: str,
        task_input: dict[str, Any],
        task_output: dict[str, Any],
        upstream_artifacts: dict[str, Any],
        prior_reviews: list[dict[str, Any]],
    ) -> dict[str, Any]:
        session_id = str(task_input.get("session_id") or "")
        self.record_event(
            "review.started",
            session_id=session_id,
            task_type=task_type,
            review_phase=review_phase,
        )
        try:
            verdict = self.review_tool.review_artifact(
                review_phase=review_phase,
                target_goal=target_goal,
                task_type=task_type,
                task_input=task_input,
                task_output=task_output,
                upstream_artifacts=upstream_artifacts,
                prior_reviews=prior_reviews,
            )
        except Exception as exc:
            self.record_event(
                "review.failed",
                session_id=session_id,
                task_type=task_type,
                review_phase=review_phase,
                error=str(exc),
            )
            raise
        parsed = ReviewVerdict(**verdict)
        self.record_event(
            "review.finished",
            session_id=session_id,
            task_type=task_type,
            review_phase=review_phase,
            approved=parsed.approved,
            signal=parsed.signal,
            blocking=parsed.blocking,
        )
        return parsed.model_dump()

    def run_virtual_agent(
        self,
        *,
        agent_type: str,
        user_payload: dict[str, Any],
        revision_mode: bool = False,
    ) -> dict[str, Any]:
        session_id = str(user_payload.get("session_id") or "")
        agent_name = str(user_payload.get("agent_name") or agent_type)
        self.record_event(
            "virtual_agent.started",
            session_id=session_id,
            task_type=agent_type,
            agent_name=agent_name,
            prompt_name=str(user_payload.get("prompt_name") or ""),
            model_role=str(user_payload.get("model_role") or ""),
        )
        try:
            result = self.review_tool.run_virtual_agent(
                agent_type=agent_type,
                agent_name=agent_name,
                prompt_name=str(user_payload.get("prompt_name") or ""),
                model_role=str(user_payload.get("model_role") or ""),
                output_contract=str(user_payload.get("output_contract") or "text_artifact"),
                stage_goal=str(user_payload.get("stage_goal") or ""),
                stage_role=str(user_payload.get("stage_role") or ""),
                input_refs=list(user_payload.get("input_refs") or []),
                allowed_input_refs=list(user_payload.get("allowed_input_refs") or []),
                resolved_inputs=dict(user_payload.get("resolved_inputs") or {}),
                input_manifest=dict(user_payload.get("input_manifest") or {}),
                artifact_refs=dict(user_payload.get("artifact_refs") or {}),
                artifact_channels=list(user_payload.get("artifact_channels") or []),
                artifact_channel_sources=dict(user_payload.get("artifact_channel_sources") or {}),
                dedupe_artifact_inputs=bool(user_payload.get("dedupe_artifact_inputs", False)),
                stage_outputs=dict(user_payload.get("stage_outputs") or {}),
                input_payload=dict(user_payload.get("input_payload") or {}),
                temperature=float(user_payload.get("temperature", 0.2) or 0.0),
                max_tokens=int(user_payload.get("max_tokens", 1800) or 0),
                user_input=str(user_payload.get("user_input") or ""),
                primary_discipline=str(user_payload.get("primary_discipline") or ""),
                conference_name=str(user_payload.get("conference_name") or ""),
                user_preferences=str(user_payload.get("user_preferences") or ""),
                document_context_summary=dict(user_payload.get("document_context_summary") or {}),
                document_excerpt=str(user_payload.get("document_excerpt") or ""),
                payload_logic=dict(user_payload.get("payload_logic") or {}),
                payload_style=dict(user_payload.get("payload_style") or {}),
                payload_mapper=dict(user_payload.get("payload_mapper") or {}),
                source_files=list(user_payload.get("source_files") or []),
                revision_context=dict(user_payload.get("revision_context") or {}),
                revision_mode=revision_mode,
            )
        except Exception as exc:
            self.record_event(
                "virtual_agent.failed",
                session_id=session_id,
                task_type=agent_type,
                agent_name=agent_name,
                error=str(exc),
            )
            raise
        self.record_event(
            "virtual_agent.finished",
            session_id=session_id,
            task_type=agent_type,
            agent_name=result.get("agent_name") or agent_name,
            prompt_name=result.get("prompt_name", ""),
            model_name=result.get("model_name", ""),
            request_api_mode=result.get("request_api_mode", ""),
            output_contract=result.get("output_contract", ""),
        )
        return result

    def save_image_artifact(self, session_id: str, image_artifact: dict[str, Any]) -> dict[str, Any]:
        value = image_artifact.setdefault("value", {})
        image_b64 = str(value.get("image_b64") or "")
        image_url = str(value.get("image_url") or "")
        if image_b64:
            import base64

            mime_type = str(value.get("image_mime_type") or "image/png").lower()
            extension = ".png"
            if "jpeg" in mime_type or "jpg" in mime_type:
                extension = ".jpg"
            elif "webp" in mime_type:
                extension = ".webp"
            file_path = self.config.output_dir / f"{session_id}{extension}"
            file_path.write_bytes(base64.b64decode(image_b64))
            value["local_path"] = str(file_path)
            value["public_url"] = f"/outputs/{file_path.name}"
        elif image_url:
            value["local_path"] = image_url
            value["public_url"] = image_url
        return image_artifact

