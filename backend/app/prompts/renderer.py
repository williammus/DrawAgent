from __future__ import annotations

import json
import re
from typing import Any

from app.core.errors import PromptRenderError


VARIABLE_PATTERN = re.compile(r"\[\[([a-zA-Z0-9_]+)\]\]")


class PromptRenderer:
    def required_variables(self, template_text: str) -> set[str]:
        return {match.group(1) for match in VARIABLE_PATTERN.finditer(template_text)}

    def render(self, template_text: str, variables: dict[str, Any]) -> str:
        required = self.required_variables(template_text)
        missing = sorted(name for name in required if name not in variables)
        if missing:
            raise PromptRenderError(
                "Prompt variables are missing.",
                details={"missing_variables": missing},
            )

        return VARIABLE_PATTERN.sub(
            lambda match: self._stringify(variables[match.group(1)]),
            template_text,
        )

    def _stringify(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)

        if value is None:
            return "null"

        return str(value)
