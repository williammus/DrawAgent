from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import ArtifactValidationError, InputValidationError
from app.graph.state import GraphState
from app.llm import LLMClient
from app.prompts import PromptRegistry, PromptRenderer
from app.schemas.agents import ControllerResponse


ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredAgentExecutor(ABC, Generic[ModelT]):
    agent_name: str
    output_model: type[ModelT]

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_registry: PromptRegistry | None = None,
        prompt_renderer: PromptRenderer | None = None,
        prompt_version: str | None = None,
        max_attempts: int = 2,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_registry = prompt_registry or PromptRegistry()
        self.prompt_renderer = prompt_renderer or PromptRenderer()
        self.prompt_version = prompt_version
        self.max_attempts = max(1, max_attempts)

    def run(self, state: GraphState) -> dict[str, Any]:
        variables = self.build_prompt_variables(state)
        template = self.prompt_registry.load_text(self.agent_name, self.prompt_version)
        prompt_text = self.prompt_renderer.render(template, variables)
        artifact = self._invoke_and_validate(prompt_text)
        return self.build_state_updates(state, artifact)

    def _invoke_and_validate(self, prompt_text: str) -> ModelT:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                payload = self.llm_client.generate_json(prompt_text)
                return self.output_model.model_validate(payload)
            except (InputValidationError,):
                raise
            except (ArtifactValidationError, ValidationError) as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    break

        raise ArtifactValidationError(
            f"{self.agent_name} returned invalid structured output.",
            details={
                "agent_name": self.agent_name,
                "attempts": self.max_attempts,
                "error": str(last_error) if last_error else None,
            },
        ) from last_error

    @abstractmethod
    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def build_state_updates(self, state: GraphState, artifact: ModelT) -> dict[str, Any]:
        raise NotImplementedError

    def require_field(self, state: GraphState, field_name: str) -> Any:
        value = state.get(field_name)
        if value is None:
            raise InputValidationError(
                f"{self.agent_name} requires field {field_name}.",
                details={"agent_name": self.agent_name, "field_name": field_name},
            )
        return value


class ControllerExecutor(ABC):
    agent_name: str

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_registry: PromptRegistry | None = None,
        prompt_renderer: PromptRenderer | None = None,
        prompt_version: str | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_registry = prompt_registry or PromptRegistry()
        self.prompt_renderer = prompt_renderer or PromptRenderer()
        self.prompt_version = prompt_version

    def run(self, state: GraphState) -> ControllerResponse:
        variables = self.build_prompt_variables(state)
        template = self.prompt_registry.load_text(self.agent_name, self.prompt_version)
        prompt_text = self.prompt_renderer.render(template, variables)
        payload = self.llm_client.generate_with_tools(
            prompt_text,
            tools=self.build_tool_schemas(),
            system_prompt=self.build_system_prompt(),
        )
        return ControllerResponse.model_validate(payload)

    @abstractmethod
    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def build_tool_schemas(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def build_system_prompt(self) -> str | None:
        return None
