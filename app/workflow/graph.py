from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.core.logging import debug_event
from app.core.message_bus import append_message, pop_next_pending_message
from app.core.state import WorkflowState
from app.tools.controller_tools import (
    dispatch_virtual_task,
    finalize_prompt,
    request_clarification,
    route_skill_decision,
    select_skill,
    trigger_image_generation,
)
from app.workflow.task_factory import build_virtual_task, next_skill_stage


class DualNodeWorkflowGraph:
    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.graph = self._build().compile()

    def run(self, state: WorkflowState) -> WorkflowState:
        return self.graph.invoke(state)

    def _build(self) -> StateGraph:
        graph = StateGraph(WorkflowState)
        graph.add_node("controller_node", self._controller_node)
        graph.add_node("virtual_worker_node", self._virtual_worker_node)
        graph.add_edge(START, "controller_node")
        graph.add_conditional_edges(
            "controller_node",
            self._route_from_controller,
            {
                "virtual_worker_node": "virtual_worker_node",
                "end": END,
            },
        )
        graph.add_edge("virtual_worker_node", "controller_node")
        return graph

    @staticmethod
    def _route_from_controller(state: WorkflowState) -> Literal["virtual_worker_node", "end"]:
        return "virtual_worker_node" if state.get("next_hop") == "worker" else "end"

    @staticmethod
    def _normalize_optional_text(value: Any) -> str:
        return str(value or "").strip()

    def _extract_design_context_from_text(self, text: str) -> dict[str, str]:
        raw = str(text or "")
        if not raw.strip():
            return {}

        patterns = {
            "primary_discipline": [
                r"(?im)^\s*(?:primary[_\-\s]?discipline|一级学科|学科|领域)\s*[:：]\s*(.+?)\s*$",
            ],
            "conference_name": [
                r"(?im)^\s*(?:conference[_\-\s]?name|venue|target[_\-\s]?venue|会议|期刊|目标会议|目标期刊)\s*[:：]\s*(.+?)\s*$",
            ],
            "user_preferences": [
                r"(?im)^\s*(?:user[_\-\s]?preferences|preferences|特殊要求|用户偏好|偏好|额外要求)\s*[:：]\s*(.+?)\s*$",
            ],
        }

        extracted: dict[str, str] = {}
        for key, regexes in patterns.items():
            for pattern in regexes:
                match = re.search(pattern, raw)
                if match:
                    extracted[key] = match.group(1).strip()
                    break
        return extracted

    def _apply_design_context(self, state: WorkflowState, updates: dict[str, Any] | None) -> WorkflowState:
        updates = updates or {}
        for key in ("primary_discipline", "conference_name", "user_preferences"):
            value = self._normalize_optional_text(updates.get(key))
            if value:
                state[key] = value
        return state

    def _current_design_context(self, state: WorkflowState) -> dict[str, str]:
        return {
            "primary_discipline": self._normalize_optional_text(state.get("primary_discipline")),
            "conference_name": self._normalize_optional_text(state.get("conference_name")),
            "user_preferences": self._normalize_optional_text(state.get("user_preferences")),
        }

    def _strip_design_context_lines(self, text: str) -> str:
        raw = str(text or "")
        if not raw.strip():
            return ""

        patterns = [
            r"(?im)^\s*(?:primary[_\-\s]?discipline|一级学科|学科|领域)\s*[:：]\s*.+$",
            r"(?im)^\s*(?:conference[_\-\s]?name|venue|target[_\-\s]?venue|会议|期刊|目标会议|目标期刊)\s*[:：]\s*.+$",
            r"(?im)^\s*(?:user[_\-\s]?preferences|preferences|特殊要求|用户偏好|偏好|额外要求)\s*[:：]\s*.+$",
        ]
        cleaned = raw
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _has_source_material(self, state: WorkflowState) -> bool:
        document_context = state.get("document_context", {}) or {}
        if self._normalize_optional_text(document_context.get("combined_excerpt")):
            return True
        if self._normalize_optional_text(document_context.get("combined_text")):
            return True

        non_design_user_text = self._strip_design_context_lines(str(state.get("user_input", "") or ""))
        normalized = re.sub(r"\s+", " ", non_design_user_text).strip()
        if len(normalized) >= 60:
            return True
        return False

    def _source_material_status(self, state: WorkflowState) -> dict[str, Any]:
        document_context = state.get("document_context", {}) or {}
        non_design_user_text = self._strip_design_context_lines(str(state.get("user_input", "") or ""))
        normalized = re.sub(r"\s+", " ", non_design_user_text).strip()
        return {
            "file_count": int(document_context.get("file_count", 0) or 0),
            "parsed_file_count": int(document_context.get("parsed_file_count", 0) or 0),
            "retrieval_ready": bool(document_context.get("retrieval_ready", False)),
            "combined_excerpt_length": len(str(document_context.get("combined_excerpt", "") or "")),
            "non_design_user_text_length": len(normalized),
        }

    def _missing_design_context_fields(self, state: WorkflowState) -> list[str]:
        context = self._current_design_context(state)
        return [key for key, value in context.items() if not value]

    @staticmethod
    def _clarification_labels() -> dict[str, str]:
        return {
            "primary_discipline": "primary_discipline",
            "conference_name": "conference_name",
            "user_preferences": "user_preferences",
        }

    def _build_design_clarification_response(
        self,
        state: WorkflowState,
        *,
        reason: str,
        question: str = "",
        missing_fields: list[str] | None = None,
    ) -> WorkflowState:
        missing_fields = list(missing_fields or self._missing_design_context_fields(state))
        labels = self._clarification_labels()
        requested = [labels.get(item, item) for item in missing_fields]
        question_text = question.strip() if question.strip() else (
            "开始科研绘图前，还需要你补充 3 项信息：\n"
            "1. primary_discipline：你的一级学科或大领域\n"
            "2. conference_name：目标期刊或会议名称\n"
            "3. user_preferences：你对图的特殊偏好或限制\n\n"
            "建议直接按下面格式回复：\n"
            "primary_discipline: ...\n"
            "conference_name: ...\n"
            "user_preferences: ..."
        )
        state["missing_clarification_fields"] = missing_fields
        state["stage"] = "clarification_needed"
        state["final_response"] = {
            "chinese_explanation": question_text,
            "reason": reason,
            "missing_fields": requested,
            "collected_values": self._current_design_context(state),
        }
        state["next_hop"] = "end"
        return state

    def _build_source_material_clarification_response(
        self,
        state: WorkflowState,
        *,
        reason: str,
    ) -> WorkflowState:
        source_status = self._source_material_status(state)
        if source_status["file_count"] > 0 and source_status["parsed_file_count"] == 0:
            question_text = (
                "开始科研绘图前，还需要可用于方法抽取的正文内容。\n"
                "当前附件虽然已上传，但系统没有解析出可用正文。\n\n"
                "请任选一种方式继续：\n"
                "1. 重新上传可解析的 PDF / DOCX / Markdown\n"
                "2. 直接粘贴论文摘要、方法部分、图注或相关正文原文\n\n"
                "只有学科、会议和偏好信息，不足以进入 logic_extraction。"
            )
        else:
            question_text = (
                "开始科研绘图前，还需要论文正文或可用于抽取方法结构的原文内容。\n\n"
                "请任选一种方式补充：\n"
                "1. 上传论文 PDF / DOCX / Markdown\n"
                "2. 直接粘贴摘要、方法部分、图注或相关正文\n\n"
                "当前仅有学科、会议和偏好信息，不足以进入 logic_extraction。"
            )
        state["stage"] = "clarification_needed"
        state["final_response"] = {
            "chinese_explanation": question_text,
            "reason": reason,
            "missing_fields": [],
            "collected_values": self._current_design_context(state),
            "source_material_required": True,
            "source_material_status": source_status,
        }
        state["next_hop"] = "end"
        return state

    def _controller_node(self, state: WorkflowState) -> dict[str, Any]:
        state = deepcopy(state)
        state.setdefault("messages", [])
        state.setdefault("completed_tasks", [])
        state.setdefault("warnings", [])
        state.setdefault("review_history", [])
        state.setdefault("artifacts", {})
        state.setdefault("stage", "initial")
        state.setdefault("primary_discipline", "")
        state.setdefault("conference_name", "")
        state.setdefault("user_preferences", "")
        state.setdefault("missing_clarification_fields", [])
        state = self._apply_design_context(
            state,
            self._extract_design_context_from_text(state.get("user_input", "")),
        )

        if state.get("awaiting_user_confirmation"):
            state["next_hop"] = "end"
            return state

        if state.get("active_task"):
            state["next_hop"] = "worker"
            return state

        pending_message, messages = pop_next_pending_message(state.get("messages", []), "controller")
        state["messages"] = messages
        if pending_message:
            debug_event("controller_message_received", message_type=pending_message.get("message_type"), task_type=pending_message.get("task_type"))
            state = self._handle_message(state, pending_message)
            if state.get("active_task"):
                state["next_hop"] = "worker"
            elif state.get("awaiting_user_confirmation") or state.get("stage") in {"clarification_needed", "completed", "image_generation_completed", "image_generation_failed", "image_generation_not_implemented"}:
                state["next_hop"] = "end"
            else:
                state["next_hop"] = "worker"
            return state

        if not state.get("selected_skill"):
            state = self._select_skill(state)
            if state.get("selected_skill") and state.get("stage") != "clarification_needed":
                state = self._dispatch_next_pipeline_stage(state)
                state["next_hop"] = "worker" if state.get("active_task") else "end"
            return state

        if state.get("stage") == "image_generation_requested":
            state = self._dispatch_image_generation(state)
            state["next_hop"] = "worker" if state.get("active_task") else "end"
            return state

        state = self._dispatch_next_pipeline_stage(state)
        state["next_hop"] = "worker" if state.get("active_task") else "end"
        return state

    def _select_skill(self, state: WorkflowState) -> WorkflowState:
        prompt = self.runtime.prompt_repository.render("controller", {})
        user_payload = {
            "mode": "select_skill",
            "user_input": state.get("user_input", ""),
            "document_context_summary": state.get("document_context_summary", {}),
            "available_skills": self.runtime.describe_skills(),
            "design_context": self._current_design_context(state),
            "required_user_fields_for_scientific_diagram": [
                "primary_discipline",
                "conference_name",
                "user_preferences",
            ],
        }
        try:
            result = self.runtime.llm_client.run_tool_call(
                model=self.runtime.config.controller_model,
                system_prompt=prompt,
                user_payload=user_payload,
                tools=[route_skill_decision],
                temperature=0.1,
                max_tokens=800,
            )
            tool_result = result["tool_result"]
        except Exception as exc:
            if state.get("document_context", {}).get("file_count", 0) or state.get("user_input", "").strip():
                tool_result = {
                    "action": "select_skill",
                    "skill_name": self.runtime.config.default_skill,
                    "reason": f"Controller fallback selected default skill due to runtime error: {exc}",
                }
            else:
                tool_result = {
                    "action": "request_clarification",
                    "question": "请先上传论文或描述你要生成的科研图内容。",
                    "reason": f"Controller fallback requested clarification due to runtime error: {exc}",
                }
        state = self._apply_design_context(state, tool_result)
        if tool_result["action"] == "request_clarification":
            return self._build_design_clarification_response(
                state,
                reason=tool_result.get("reason", ""),
                question=tool_result.get("question", ""),
                missing_fields=tool_result.get("missing_fields", []),
            )

        skill = self.runtime.skill_repository.get(tool_result["skill_name"])
        state["selected_skill"] = skill.name
        state["skill_plan"] = deepcopy(skill.plan)
        if skill.name == "scientific_diagram":
            missing_fields = self._missing_design_context_fields(state)
            if missing_fields:
                return self._build_design_clarification_response(
                    state,
                    reason="scientific_diagram 在 logic_extraction 前需要用户明确提供学科、目标会议/期刊、以及个人风格偏好。",
                    missing_fields=missing_fields,
                )
            if not self._has_source_material(state):
                return self._build_source_material_clarification_response(
                    state,
                    reason="scientific_diagram 在 logic_extraction 前必须先拿到论文正文、摘要、方法部分或其他可用于抽取结构的原文内容。",
                )
            state["missing_clarification_fields"] = []
        state["stage"] = "skill_selected"
        debug_event("skill_selected", skill_name=skill.name, reason=tool_result.get("reason", ""))
        return state

    def _dispatch_next_pipeline_stage(self, state: WorkflowState) -> WorkflowState:
        if state.get("selected_skill") == "scientific_diagram":
            missing_fields = self._missing_design_context_fields(state)
            if missing_fields:
                return self._build_design_clarification_response(
                    state,
                    reason="scientific_diagram 在进入后续虚拟节点前需要完整的用户学科、目标会议/期刊和偏好信息。",
                    missing_fields=missing_fields,
                )
            if not self._has_source_material(state):
                return self._build_source_material_clarification_response(
                    state,
                    reason="scientific_diagram 在进入 logic_extraction 前缺少可抽取方法结构的正文内容。",
                )

        next_stage = next_skill_stage(
            state.get("skill_plan", []),
            state.get("completed_tasks", []),
            include_image_generation=False,
        )
        if next_stage is None:
            if str(state.get("artifacts", {}).get("payload_final", {}).get("value", "") or "").strip():
                checkpoint_id, checkpoint_path = self.runtime.save_prompt_checkpoint(state)
                state["prompt_checkpoint_id"] = checkpoint_id
                state["prompt_checkpoint_path"] = checkpoint_path
                state["awaiting_user_confirmation"] = True
                state["stage"] = "awaiting_user_confirmation"
                state["next_hop"] = "end"
            else:
                state["stage"] = "completed"
                state["next_hop"] = "end"
            return state

        prompt = self.runtime.prompt_repository.render("controller", {})
        user_payload = {
            "mode": "dispatch_next_task",
            "selected_skill": state.get("selected_skill", ""),
            "next_stage_candidate": next_stage,
            "completed_tasks": state.get("completed_tasks", []),
            "warnings": state.get("warnings", []),
        }
        try:
            result = self.runtime.llm_client.run_tool_call(
                model=self.runtime.config.controller_model,
                system_prompt=prompt,
                user_payload=user_payload,
                tools=[dispatch_virtual_task],
                temperature=0.1,
                max_tokens=600,
            )
            tool_result = result["tool_result"]
        except Exception as exc:
            tool_result = {
                "action": "dispatch_virtual_task",
                "task_type": next_stage["stage"],
                "reason": f"Controller fallback dispatched next stage due to runtime error: {exc}",
                "revision_mode": False,
                "release_after_failure": False,
            }

        active_task = build_virtual_task(
            stage_spec=next_stage,
            max_retry=self.runtime.config.max_review_rounds,
            revision_mode=bool(tool_result.get("revision_mode", False)),
        )
        state["active_task"] = active_task
        state["pending_tasks"] = state.get("pending_tasks", []) + [active_task]
        state["stage"] = active_task["task_type"]
        debug_event("task_dispatched", task_type=active_task["task_type"], revision_mode=active_task["revision_mode"])
        return state

    def _dispatch_image_generation(self, state: WorkflowState) -> WorkflowState:
        prompt = self.runtime.prompt_repository.render("controller", {})
        user_payload = {
            "mode": "trigger_image_generation",
            "checkpoint_id": state.get("prompt_checkpoint_id", ""),
            "payload_final": state.get("artifacts", {}).get("payload_final", {}),
        }
        try:
            result = self.runtime.llm_client.run_tool_call(
                model=self.runtime.config.controller_model,
                system_prompt=prompt,
                user_payload=user_payload,
                tools=[trigger_image_generation],
                temperature=0.0,
                max_tokens=300,
            )
            _ = result["tool_result"]
        except Exception:
            pass

        stage_spec = {
            "stage": "image_generation",
            "agent_name": "image_generation",
            "review_required": False,
        }
        state["active_task"] = build_virtual_task(
            stage_spec=stage_spec,
            max_retry=0,
            revision_mode=False,
        )
        state["pending_tasks"] = state.get("pending_tasks", []) + [state["active_task"]]
        return state

    def _handle_message(self, state: WorkflowState, message: dict[str, Any]) -> WorkflowState:
        task_type = str(message.get("task_type") or "")
        message_type = str(message.get("message_type") or "")
        payload = message.get("payload") or {}

        if message_type == "positive_check":
            debug_event("task_approved", task_type=task_type, stage=state.get("stage", ""))
            state["completed_tasks"] = state.get("completed_tasks", []) + [
                {"task_type": task_type, "status": "approved"}
            ]
            if task_type == "summarization":
                prompt = self.runtime.prompt_repository.render("controller", {})
                summary_text = str(state.get("artifacts", {}).get("payload_final", {}).get("value", "") or "").strip()
                user_payload = {
                    "mode": "finalize_prompt",
                    "payload_final": state.get("artifacts", {}).get("payload_final", {}),
                    "review_history_tail": state.get("review_history", [])[-1:],
                }
                try:
                    result = self.runtime.llm_client.run_tool_call(
                        model=self.runtime.config.controller_model,
                        system_prompt=prompt,
                        user_payload=user_payload,
                        tools=[finalize_prompt],
                        temperature=0.0,
                        max_tokens=600,
                    )
                    tool_result = result["tool_result"]
                except Exception as exc:
                    tool_result = {
                        "action": "finalize_prompt",
                        "chinese_explanation": (
                            "已生成一版可直接用于科研绘图的英文 Prompt，请确认后开始生图。"
                            if summary_text
                            else f"Prompt 已生成，请确认后继续。({exc})"
                        ),
                        "release_with_warnings": False,
                        "warning_note": "",
                    }
                state["final_response"] = {
                    "chinese_explanation": tool_result["chinese_explanation"],
                    "review_warning": "",
                    "review_status": "approved",
                    "review_approved": True,
                    "latest_review_feedback": state.get("review_history", [])[-1] if state.get("review_history") else {},
                }
                checkpoint_id, checkpoint_path = self.runtime.save_prompt_checkpoint(state)
                state["prompt_checkpoint_id"] = checkpoint_id
                state["prompt_checkpoint_path"] = checkpoint_path
                state["awaiting_user_confirmation"] = True
                state["stage"] = "awaiting_user_confirmation"
                debug_event(
                    "prompt_ready",
                    checkpoint_id=checkpoint_id,
                    released_with_warnings=state.get("released_with_warnings", False),
                )
                return state

            if task_type == "image_generation":
                state["completed_tasks"] = state.get("completed_tasks", []) + [
                    {"task_type": "image_generation", "status": "approved"}
                ]
                state["stage"] = "image_generation_completed"
                state["next_hop"] = "end"
                return state

            state["stage"] = f"{task_type}_approved"
            return self._dispatch_next_pipeline_stage(state)

        if message_type == "image_generation_failed":
            warning = str(payload.get("warning") or "图片生成失败。")
            debug_event(
                "image_generation_failed",
                task_type=task_type,
                warning=warning,
            )
            state["warnings"] = state.get("warnings", []) + [warning]
            state["stage"] = "image_generation_failed"
            state["next_hop"] = "end"
            return state

        if message_type == "negative_review":
            review = payload.get("review") or {}
            debug_event(
                "review_rejected",
                task_type=task_type,
                retry_count=(payload.get("task") or {}).get("retry_count", 0),
                max_retry=(payload.get("task") or {}).get("max_retry", self.runtime.config.max_review_rounds),
                issues=review.get("issues", []),
            )
            state["review_history"] = state.get("review_history", []) + [review]
            active_task = payload.get("task") or {}
            retry_count = int(active_task.get("retry_count", 0))
            max_retry = int(active_task.get("max_retry", self.runtime.config.max_review_rounds))

            if retry_count < max_retry:
                prompt = self.runtime.prompt_repository.render("controller", {})
                try:
                    result = self.runtime.llm_client.run_tool_call(
                        model=self.runtime.config.controller_model,
                        system_prompt=prompt,
                        user_payload={
                            "mode": "handle_negative_review",
                            "task_type": task_type,
                            "retry_count": retry_count,
                            "max_retry": max_retry,
                            "review": review,
                        },
                        tools=[dispatch_virtual_task, finalize_prompt],
                        temperature=0.1,
                        max_tokens=600,
                    )
                    tool_result = result["tool_result"]
                except Exception:
                    tool_result = {
                        "action": "dispatch_virtual_task",
                        "task_type": task_type,
                        "reason": "Retry same task after negative review.",
                        "revision_mode": True,
                        "release_after_failure": False,
                    }

                if tool_result["action"] == "dispatch_virtual_task":
                    stage_spec = next(
                        item for item in state.get("skill_plan", [])
                        if item.get("stage") == task_type
                    )
                    revision_context = {
                        "original_input": payload.get("task_input", {}),
                        "current_output": payload.get("task_output", {}),
                        "review_feedback": review,
                    }
                    state["active_task"] = build_virtual_task(
                        stage_spec=stage_spec,
                        max_retry=max_retry,
                        retry_count=retry_count + 1,
                        revision_mode=True,
                        revision_context=revision_context,
                    )
                    state["pending_tasks"] = state.get("pending_tasks", []) + [state["active_task"]]
                    state["stage"] = f"{task_type}_retrying"
                    debug_event(
                        "revision_scheduled",
                        task_type=task_type,
                        next_retry_count=retry_count + 1,
                        max_retry=max_retry,
                    )
                    return state

            warning = f"{task_type} 超过最大审查轮次，当前结果未通过审查，已带 warning 放行。"
            state["warnings"] = state.get("warnings", []) + [warning]
            state["released_with_warnings"] = True
            debug_event(
                "warning_release",
                task_type=task_type,
                warning=warning,
                review_phase=review.get("review_phase", ""),
            )
            state["completed_tasks"] = state.get("completed_tasks", []) + [
                {"task_type": task_type, "status": "released_with_warnings"}
            ]
            if task_type == "summarization":
                state["final_response"] = {
                    "chinese_explanation": "已生成一版英文绘图 Prompt，但该版本尚未通过审查，请先自行检查后再决定是否生图。",
                    "review_warning": warning,
                    "review_status": "not_approved_but_released",
                    "review_approved": False,
                    "latest_review_feedback": review,
                }
                checkpoint_id, checkpoint_path = self.runtime.save_prompt_checkpoint(state)
                state["prompt_checkpoint_id"] = checkpoint_id
                state["prompt_checkpoint_path"] = checkpoint_path
                state["awaiting_user_confirmation"] = True
                state["stage"] = "awaiting_user_confirmation"
                debug_event(
                    "prompt_ready",
                    checkpoint_id=checkpoint_id,
                    released_with_warnings=True,
                )
                return state

            return self._dispatch_next_pipeline_stage(state)

        return state

    def _fallback_worker_artifact(self, state: WorkflowState, task: dict[str, Any]) -> dict[str, Any]:
        task_type = str(task["task_type"])
        summary = state.get("document_context_summary", {})
        excerpt = str(state.get("document_context", {}).get("combined_excerpt", "") or "")
        user_input = str(state.get("user_input", "") or "")

        if task_type == "logic_extraction":
            if not excerpt.strip():
                return {
                    "key": "logician",
                    "value": (
                        "1. 核心方法描述 (Core Method Description)\n"
                        "- 当前输入仅包含学科/会议/偏好或过于概括的需求，缺少可用于抽取方法结构的论文正文。\n\n"
                        "2. 方法结构图对应的目标图表标题 (Target Chart Title)\n"
                        "- 待补充（缺少原文内容）\n\n"
                        "3. 逻辑流验证 (Logical Flow)\n"
                        "[Step 1] 输入: 待补充 -> 技术: 待补充 -> 输出: 待补充\n\n"
                        "4. 关键实体提取 (Key Entities)\n"
                        "- 待补充（缺少原文内容，无法提取具体组件与依赖关系）\n\n"
                        "5. 绘图必须保留的依赖关系 (Mandatory Dependencies)\n"
                        "- 待补充（缺少原文内容）\n\n"
                        "6. 可视化重点提示 (Figure-critical Notes)\n"
                        "- 请先提供论文摘要、方法部分、图注或上传可解析附件。"
                    ),
                }
            return {
                "key": "logician",
                "value": (
                    "1. 逻辑流验证 (Logical Flow)\n"
                    f"{excerpt[:1200] or user_input[:600] or '待根据附件提炼具体方法结构。'}\n\n"
                    "2. 关键实体提取 (Key Entities)\n"
                    "- Input Context\n"
                    "- Core Method\n"
                    "- Output\n\n"
                    "3. 目标图标题 (Target Figure Title)\n"
                    "- Scientific Diagram Draft\n\n"
                    "4. 核心方法描述 (Core Method Summary)\n"
                    f"- {excerpt[:500] or user_input[:300] or 'Method summary unavailable.'}\n\n"
                    "5. 绘图必须保留的依赖关系 (Mandatory Dependencies)\n"
                    "- Input Context feeds into Core Method\n"
                    "- Core Method produces Output\n\n"
                    f"Source refs: {', '.join(item.get('name') for item in summary.get('files', []) if item.get('name'))}"
                ),
            }
        if task_type == "style_extraction":
            return {
                "key": "style_designer",
                "value": (
                    f"Primary discipline: {state.get('primary_discipline', '') or 'computer science'}\n"
                    "Specialized field: scientific diagram\n"
                    f"Target venue: {state.get('conference_name', '') or 'top-tier conference'}\n\n"
                    "Palette\n"
                    "- #1F2937 - primary text and borders\n"
                    "- #334155 - secondary module emphasis\n"
                    "- #64748B - grouping outlines and helper connectors\n"
                    "- #E2E8F0 - subtle background containers\n"
                    "- #F8FAFC - canvas background\n\n"
                    "Typography\n"
                    "- Title font: bold sans-serif\n"
                    "- Body font: clean sans-serif\n\n"
                    "Shape rules\n"
                    "- Input/data: parallelogram\n"
                    "- Core modules: rounded rectangle\n"
                    "- Loss/scoring: diamond\n"
                    "- Outputs: ellipse\n\n"
                    "Layout preferences\n"
                    "- Left-to-right flow\n"
                    "- Clear grouping\n"
                    "- Consistent spacing\n\n"
                    "Negative rules\n"
                    "- No photorealism\n"
                    "- No heavy shadows\n"
                    "- No decorative clutter"
                ),
            }
        if task_type == "visual_mapping":
            logic_value = str(state.get("artifacts", {}).get("payload_logic", {}).get("value", "") or "").strip()
            return {
                "key": "visual_mapper",
                "value": (
                    "Canvas: 1536x1024, white background.\n"
                    "Main layout: left-to-right primary flow with one dominant center lane.\n"
                    "Grouping: use subtle bounded containers to separate input, core method, and output regions.\n"
                    "Placement rule: keep the main method block centered, let supporting branches sit above or below the main lane, and avoid edge crossings.\n"
                    "Legend: include only when connector semantics such as dashed supervision or training feedback need explanation.\n"
                    "Logic reference:\n"
                    f"{logic_value[:1600] or 'Use the logic artifact as the source of truth for module ordering and dependencies.'}"
                ),
            }
        if task_type == "summarization":
            logic_value = str(state.get("artifacts", {}).get("payload_logic", {}).get("value", "") or "").strip()
            style_value = str(state.get("artifacts", {}).get("payload_style", {}).get("value", "") or "").strip()
            mapper_value = str(state.get("artifacts", {}).get("payload_mapper", {}).get("value", "") or "").strip()
            return {
                "key": "summarizer",
                "value": (
                    "Create a professional, publication-ready scientific architecture diagram in a clean flat 2D vector style. "
                    "Use a structured academic composition, readable labels, clear hierarchy, and strict alignment. "
                    "Preserve the actual method logic from the source material instead of collapsing it into a generic pipeline. "
                    f"Logic requirements: {logic_value[:1200] or 'show a faithful progression from input through core method to outputs'}. "
                    f"Style requirements: {style_value[:900] or 'use subdued conference-style colors, concise labels, and no decorative clutter'}. "
                    f"Layout requirements: {mapper_value[:900] or 'arrange the figure with a clear left-to-right flow and grouped sections'}. "
                    "Avoid 3D effects, photorealism, glossy rendering, poster-style gradients, heavy shadows, and crowded text."
                ),
            }
        raise RuntimeError(f"Unsupported fallback task type: {task_type}")

    def _build_worker_payload(self, state: WorkflowState, task: dict[str, Any]) -> dict[str, Any]:
        task_type = task["task_type"]
        payload = {
            "user_input": state.get("user_input", ""),
            "primary_discipline": state.get("primary_discipline", ""),
            "conference_name": state.get("conference_name", ""),
            "user_preferences": state.get("user_preferences", ""),
            "document_context_summary": state.get("document_context_summary", {}),
            "document_excerpt": state.get("document_context", {}).get("combined_excerpt", ""),
            "payload_logic": state.get("artifacts", {}).get("payload_logic", {}),
            "payload_style": state.get("artifacts", {}).get("payload_style", {}),
            "payload_mapper": state.get("artifacts", {}).get("payload_mapper", {}),
            "source_files": [
                item.get("name") for item in state.get("document_context", {}).get("files", [])
            ],
        }
        if task.get("revision_mode"):
            payload["revision_context"] = task.get("revision_context", {})
        if task_type == "image_generation":
            payload = {
                "english_prompt": str(state.get("artifacts", {}).get("payload_final", {}).get("value", "") or ""),
                "checkpoint_id": state.get("prompt_checkpoint_id", ""),
                "image_attempt_id": state.get("image_attempt_id", ""),
            }
        return payload

    def _virtual_worker_node(self, state: WorkflowState) -> dict[str, Any]:
        state = deepcopy(state)
        task = deepcopy(state.get("active_task") or {})
        if not task:
            state["next_hop"] = "end"
            return state

        task_type = str(task["task_type"])
        debug_event("worker_started", task_type=task_type, retry_count=task.get("retry_count", 0), revision_mode=task.get("revision_mode", False))
        pending_tasks = [item for item in state.get("pending_tasks", []) if item.get("task_id") != task.get("task_id")]
        state["pending_tasks"] = pending_tasks
        state["active_task"] = None

        if task_type == "image_generation":
            image_warning = ""
            image_attempt_id = str(state.get("image_attempt_id") or task.get("task_id") or "")
            try:
                image_result = self.runtime.image_client.generate_image(
                    model=self.runtime.config.image_model,
                    prompt=str(state.get("artifacts", {}).get("payload_final", {}).get("value", "") or ""),
                    size="1536x1024",
                    image_attempt_id=image_attempt_id,
                )
            except Exception as exc:
                image_result = {
                    "image_url": "",
                    "image_b64": "",
                    "image_mime_type": "image/png",
                    "revised_prompt": f"Image generation fallback used: {exc}",
                    "raw_json": {},
                    "image_attempt_id": image_attempt_id,
                }
                image_warning = f"图片模型未成功返回结果：{exc}"
                state["warnings"] = state.get("warnings", []) + [image_warning]
            artifact = {
                "key": "image_generator",
                "value": image_result,
            }
            artifact = self.runtime.save_image_artifact(state["session_id"], artifact)
            state["artifacts"]["image_result"] = artifact
            if artifact.get("value", {}).get("public_url") or artifact.get("value", {}).get("image_url"):
                state["messages"] = append_message(
                    state.get("messages", []),
                    from_role="virtual_worker",
                    to_role="controller",
                    message_type="positive_check",
                    task_id=task["task_id"],
                    task_type=task_type,
                    summary="Image generation completed.",
                    payload={"artifact": artifact},
                )
                state["stage"] = "image_generation_completed"
            else:
                state["messages"] = append_message(
                    state.get("messages", []),
                    from_role="virtual_worker",
                    to_role="controller",
                    message_type="image_generation_failed",
                    task_id=task["task_id"],
                    task_type=task_type,
                    summary="Image generation failed.",
                    payload={
                        "artifact": artifact,
                        "warning": image_warning or "图片生成失败，未返回可显示图片。",
                    },
                )
                state["stage"] = "image_generation_failed"
            return state

        user_payload = self._build_worker_payload(state, task)
        try:
            result = self.runtime.run_virtual_agent(
                agent_type=task_type,
                user_payload=user_payload,
                revision_mode=bool(task.get("revision_mode", False)),
            )
            artifact = result["artifact"]
            debug_event(
                "worker_completed_via_mcp",
                task_type=task_type,
                selection_source=result.get("selection_source", ""),
                model_name=result.get("model_name", ""),
                request_api_mode=result.get("request_api_mode", ""),
                prompt_name=result.get("prompt_name", ""),
            )
        except Exception as exc:
            artifact = self._fallback_worker_artifact(state, task)
            debug_event("worker_fallback_used", task_type=task_type, reason=str(exc))
        state["artifacts"][task["output_ref"]] = artifact

        review = self.runtime.run_review(
            review_phase=str(task.get("review_phase") or ""),
            target_goal=f"Review the {task_type} output before the workflow continues.",
            task_type=task_type,
            task_input=user_payload,
            task_output=artifact,
            upstream_artifacts={
                "payload_logic": state.get("artifacts", {}).get("payload_logic", {}),
                "payload_style": state.get("artifacts", {}).get("payload_style", {}),
                "payload_mapper": state.get("artifacts", {}).get("payload_mapper", {}),
            },
            prior_reviews=state.get("review_history", []),
        )
        debug_event(
            "review_completed",
            task_type=task_type,
            review_phase=review.get("review_phase", ""),
            approved=review.get("approved", False),
            blocking=review.get("blocking", False),
            issues=review.get("issues", []),
        )
        state["review_history"] = state.get("review_history", []) + [review]
        if review["approved"]:
            state["messages"] = append_message(
                state.get("messages", []),
                from_role="review_tool",
                to_role="controller",
                message_type="positive_check",
                task_id=task["task_id"],
                task_type=task_type,
                summary=f"{task_type} passed review.",
                payload={"review": review, "artifact": artifact},
            )
        else:
            state["messages"] = append_message(
                state.get("messages", []),
                from_role="review_tool",
                to_role="controller",
                message_type="negative_review",
                task_id=task["task_id"],
                task_type=task_type,
                summary=f"{task_type} failed review.",
                payload={
                    "review": review,
                    "task": task,
                    "task_input": user_payload,
                    "task_output": artifact,
                },
            )
        state["next_hop"] = "controller"
        return state

