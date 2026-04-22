from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.checkpoint_store import CheckpointStore
from app.core.config import AppConfig
from app.core.logging import debug_event
from app.core.models import ReviewVerdict
from app.core.state import WorkflowState
from app.llm.openai_client import OpenAICompatibleClient
from app.prompts.repository import PromptRepository
from app.skills.repository import SkillRepository
from app.tools.review_tool import ReviewToolClient
from app.workflow.graph import DualNodeWorkflowGraph


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
        self.graph_runner = DualNodeWorkflowGraph(self)

    def describe_agents(self) -> list[dict[str, Any]]:
        controller_llm = self.config.llm_role("controller")
        logic_llm = self.config.llm_role("logic_extraction")
        style_llm = self.config.llm_role("style_extraction")
        mapper_llm = self.config.llm_role("visual_mapping")
        summary_llm = self.config.llm_role("summarization")
        reviewer_llm = self.config.llm_role("reviewer")
        return [
            {
                "name": "controller",
                "model": controller_llm.model,
                "role": "主控节点",
                "mode": "tool_call",
                "request_api_mode": controller_llm.api_mode,
            },
            {
                "name": "logic_extraction",
                "model": logic_llm.model,
                "role": "逻辑提取虚拟节点",
                "mode": "tool_call",
                "request_api_mode": logic_llm.api_mode,
            },
            {
                "name": "style_extraction",
                "model": style_llm.model,
                "role": "风格提取虚拟节点",
                "mode": "tool_call",
                "request_api_mode": style_llm.api_mode,
            },
            {
                "name": "visual_mapping",
                "model": mapper_llm.model,
                "role": "可视化布局虚拟节点",
                "mode": "tool_call",
                "request_api_mode": mapper_llm.api_mode,
            },
            {
                "name": "summarization",
                "model": summary_llm.model,
                "role": "总结虚拟节点",
                "mode": "tool_call",
                "request_api_mode": summary_llm.api_mode,
            },
            {
                "name": "reviewer",
                "model": reviewer_llm.model,
                "role": "MCP 审查工具",
                "mode": "mcp_tool_call",
                "request_api_mode": reviewer_llm.api_mode,
            },
        ]

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
            ],
            "messages": [
                "positive_check",
                "negative_review",
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
                        {"stage": "logic_extraction", "actor": "virtual_worker"},
                        {"stage": "style_extraction", "actor": "virtual_worker"},
                        {"stage": "visual_mapping", "actor": "virtual_worker"},
                        {"stage": "summarization", "actor": "virtual_worker"},
                        {"stage": "image_generation", "actor": "virtual_worker"},
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
            "skill_plan": [],
            "messages": [],
            "pending_tasks": [],
            "active_task": None,
            "completed_tasks": [],
            "artifacts": {
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

    def start_prompt_pipeline(
        self,
        *,
        session_id: str,
        user_input: str,
        document_context: dict[str, Any],
    ) -> WorkflowResult:
        final_state = self.graph_runner.run(
            self.build_initial_state(
                session_id=session_id,
                user_input=user_input,
                document_context=document_context,
            )
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

    def confirm_image_generation(self, checkpoint_id: str) -> dict[str, Any]:
        checkpoint = self.checkpoint_store.load(checkpoint_id)
        state = checkpoint["workflow_state"]
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
        final_state = self.graph_runner.run(state)
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
        verdict = self.review_tool.review_artifact(
            review_phase=review_phase,
            target_goal=target_goal,
            task_type=task_type,
            task_input=task_input,
            task_output=task_output,
            upstream_artifacts=upstream_artifacts,
            prior_reviews=prior_reviews,
        )
        parsed = ReviewVerdict(**verdict)
        return parsed.model_dump()

    def run_virtual_agent(
        self,
        *,
        agent_type: str,
        user_payload: dict[str, Any],
        revision_mode: bool = False,
    ) -> dict[str, Any]:
        return self.review_tool.run_virtual_agent(
            agent_type=agent_type,
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
