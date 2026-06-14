from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

_RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "chapter_candidate_rules.yaml"


@dataclass(frozen=True)
class CandidateTypeResolution:
    candidate_type: str
    suggested_knowledge_type: str | None = None


_CACHE: dict[str, Any] | None = None


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """
    Minimal fallback parser for key-value YAML-like mappings.
    Supports the subset used by chapter_candidate_rules.yaml.
    """
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().strip("'\"")
        value = value.strip()
        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent + 2, child))
            continue
        lowered = value.lower()
        if lowered in {"null", "~", "none"}:
            parsed: Any = None
        elif value.startswith(("'", '"')) and value.endswith(("'", '"')):
            parsed = value[1:-1]
        else:
            parsed = value
        current[key] = parsed
    return root


def _load_rules() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    raw_text = _RULES_PATH.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        payload = _parse_minimal_yaml(raw_text)

    if not isinstance(payload, dict):
        raise ValueError("chapter candidate rules must be an object")
    payload.setdefault("default", {"candidate_type": "ignore", "suggested_knowledge_type": None})
    payload.setdefault("rules", {})
    _CACHE = payload
    return payload


def resolve_candidate_type(*, taxonomy_code: str | None) -> CandidateTypeResolution:
    rules = _load_rules()
    fallback = rules.get("default", {})
    mapping = rules.get("rules", {})

    code = (taxonomy_code or "").strip()
    hit = mapping.get(code) if isinstance(mapping, dict) else None
    selected = hit if isinstance(hit, dict) else fallback
    candidate_type = str(selected.get("candidate_type") or "ignore")
    knowledge_type = selected.get("suggested_knowledge_type")
    return CandidateTypeResolution(
        candidate_type=candidate_type,
        suggested_knowledge_type=str(knowledge_type) if knowledge_type is not None else None,
    )
