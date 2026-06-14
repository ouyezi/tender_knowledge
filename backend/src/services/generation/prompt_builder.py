from __future__ import annotations

import json

from src.schemas.generation import ResolvedGenerationContext
from src.services.generation.prompt_seed import SYSTEM_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE


class PromptBuilder:
    def __init__(
        self,
        *,
        system_prompt_template: str = SYSTEM_PROMPT_TEMPLATE,
        user_prompt_template: str = USER_PROMPT_TEMPLATE,
    ) -> None:
        self.system_prompt_template = system_prompt_template
        self.user_prompt_template = user_prompt_template

    def build(
        self,
        resolved: ResolvedGenerationContext,
        variable_values: dict[str, str],
        *,
        target_outline_node: dict | None = None,
    ) -> tuple[str, str]:
        layers_text = "\n".join(
            [
                f"L1 rejection_clauses:\n{json.dumps(resolved.layers.get('rejection_clauses', []), ensure_ascii=False)}",
                f"L2 score_points:\n{json.dumps(resolved.layers.get('score_points', []), ensure_ascii=False)}",
                f"L3 outline_structure:\n{json.dumps(resolved.layers.get('outline_structure', []), ensure_ascii=False)}",
                f"L4 user_selections:\n{json.dumps(resolved.layers.get('user_selections', []), ensure_ascii=False)}",
                f"L5 knowledge_pack:\n{json.dumps(resolved.layers.get('knowledge_pack', []), ensure_ascii=False)}",
                f"L6 template_hints:\n{json.dumps(resolved.layers.get('template_hints', []), ensure_ascii=False)}",
            ]
        )
        source_catalog_text = json.dumps(
            [item.model_dump(mode="json") for item in resolved.source_catalog],
            ensure_ascii=False,
            indent=2,
        )
        user_prompt = self.user_prompt_template.format(
            target_outline_node=json.dumps(target_outline_node or {}, ensure_ascii=False),
            layers=layers_text,
            source_catalog=source_catalog_text,
            variable_values=json.dumps(variable_values, ensure_ascii=False),
        )
        return self.system_prompt_template, user_prompt
