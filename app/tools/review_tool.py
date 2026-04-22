from __future__ import annotations

from typing import Any

from app.core.config import AppConfig
from app.mcp.stdio_client import MCPStdIOClient


class ReviewToolClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with MCPStdIOClient(
            command=self.config.review_mcp_command,
            args=self.config.review_mcp_args,
            cwd=self.config.root_dir,
            timeout_seconds=self.config.review_mcp_timeout_seconds,
        ) as client:
            return client.call_tool(name, arguments)

    def review_artifact(
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
        return self._call_tool(
            "review_artifact",
            {
                "review_phase": review_phase,
                "target_goal": target_goal,
                "task_type": task_type,
                "task_input": task_input,
                "task_output": task_output,
                "upstream_artifacts": upstream_artifacts,
                "prior_reviews": prior_reviews,
            },
        )

    def run_virtual_agent(
        self,
        *,
        agent_type: str,
        user_input: str,
        primary_discipline: str,
        conference_name: str,
        user_preferences: str,
        document_context_summary: dict[str, Any],
        document_excerpt: str,
        payload_logic: dict[str, Any],
        payload_style: dict[str, Any],
        payload_mapper: dict[str, Any],
        source_files: list[str],
        revision_context: dict[str, Any],
        revision_mode: bool,
    ) -> dict[str, Any]:
        return self._call_tool(
            "run_virtual_agent",
            {
                "agent_type": agent_type,
                "user_input": user_input,
                "primary_discipline": primary_discipline,
                "conference_name": conference_name,
                "user_preferences": user_preferences,
                "document_context_summary": document_context_summary,
                "document_excerpt": document_excerpt,
                "payload_logic": payload_logic,
                "payload_style": payload_style,
                "payload_mapper": payload_mapper,
                "source_files": source_files,
                "revision_context": revision_context,
                "revision_mode": revision_mode,
            },
        )
