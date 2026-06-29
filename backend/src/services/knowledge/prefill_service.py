"""LLM-based knowledge attribute prefill for Knowledge V2 entry workflow."""

from __future__ import annotations

import json
import logging
import re
import socket
import urllib.error
import urllib.request
from typing import Any

from src.config import settings
from src.services.knowledge.knowledge_prefill_context import build_user_prompt
from src.services.knowledge.knowledge_prefill_prompt import build_system_prompt
from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS
from src.services.knowledge.qualification_field_utils import (
    earliest_expire_date_from_qualification_info,
    normalize_qualification_info,
)

logger = logging.getLogger(__name__)

_KNOWLEDGE_TYPES = frozenset({"fact", "certificate", "template", "solution", "case", "table", "image"})
_CONTENT_TYPES = frozenset({"text", "mixed"})
_STATUSES = frozenset({"draft", "active", "deprecated", "disabled"})
_SECURITY_LEVELS = frozenset({"public", "internal", "confidential"})
_REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})
_TEMPLATE_TYPES = frozenset(
    {
        "commitment",
        "authorization",
        "response",
        "technical_solution",
        "implementation_plan",
        "service_plan",
        "quotation",
    }
)

_DEFAULT_ENUMS: dict[str, str] = {
    "knowledge_type": "fact",
    "content_type": "text",
    "status": "draft",
    "security_level": "internal",
    "review_status": "approved",
    "block_type_code": "product_solution",
    "application_type_code": "preferred_reference",
}
_DEFAULT_BUSINESS_LINE_CODES = ["general"]


def prefill_knowledge_attributes(*, content: str, metadata: dict) -> dict:
    """Prefill editable knowledge attributes from chapter content via LLM."""
    partial = _build_partial_result(metadata)
    if not settings.llm_enabled:
        partial["warnings"] = ["prefill_failed"]
        return partial

    try:
        raw = _chat_with_timeout(
            system_prompt=build_system_prompt(),
            user_prompt=build_user_prompt(content=content, context=metadata or {}),
        )
        parsed = _parse_llm_json(raw)
        if parsed is None:
            partial["warnings"] = ["prefill_failed"]
            return partial
        return _normalize_prefill(parsed, metadata)
    except TimeoutError:
        partial["warnings"] = ["prefill_timeout"]
        return partial
    except Exception as exc:
        logger.warning("Knowledge prefill failed: %s", exc)
        partial["warnings"] = ["prefill_failed"]
        return partial


def _chat_with_timeout(*, system_prompt: str, user_prompt: str) -> str:
    """Call OpenAI-compatible chat API with prefill model and dedicated timeout."""
    payload: dict[str, Any] = {
        "model": settings.knowledge_prefill_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=settings.knowledge_prefill_timeout_sec
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"])
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise TimeoutError("prefill request timed out") from exc
        raise


def _parse_llm_json(content: str) -> dict | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _build_partial_result(metadata: dict) -> dict:
    result = {
        "title": metadata.get("chapter_title") or "",
        "summary": None,
        "tags": [],
        "business_line_codes": list(_DEFAULT_BUSINESS_LINE_CODES),
        "regions": [],
        "qualification_info": None,
        "expire_date": None,
        "is_template": False,
        "template_type": None,
    }
    for key, default in _DEFAULT_ENUMS.items():
        result[key] = _enum_or_default(metadata.get(key), key, default)
    if metadata.get("content_type_hint") == "mixed":
        result["content_type"] = "mixed"
    if metadata.get("file_name"):
        result["file_name"] = str(metadata["file_name"])
    return result


def _normalize_prefill(parsed: dict, metadata: dict) -> dict:
    result = _build_partial_result(metadata)
    if parsed.get("title") is not None:
        title = str(parsed.get("title") or "").strip()
        result["title"] = title or result["title"]
    if parsed.get("summary") is not None:
        summary = parsed.get("summary")
        result["summary"] = str(summary) if summary else None

    for field in _DEFAULT_ENUMS:
        if field in parsed and parsed[field] is not None:
            result[field] = _enum_or_default(parsed.get(field), field, _DEFAULT_ENUMS[field])

    result["tags"] = _as_str_list(parsed.get("tags"))
    result["business_line_codes"] = _business_line_codes_or_default(
        parsed.get("business_line_codes")
    )
    result["regions"] = _as_str_list(parsed.get("regions"))
    date_confidence = str(parsed.get("date_confidence") or "").strip().lower()
    if date_confidence == "high":
        result["qualification_info"] = normalize_qualification_info(parsed.get("qualification_info"))
        derived = earliest_expire_date_from_qualification_info(result["qualification_info"])
        result["expire_date"] = derived.isoformat() if derived else None
    else:
        result["qualification_info"] = None
        result["expire_date"] = None
    result["is_template"] = bool(parsed.get("is_template", result["is_template"]))

    template_type = parsed.get("template_type")
    if template_type is not None:
        normalized = str(template_type).strip().lower()
        result["template_type"] = normalized if normalized in _TEMPLATE_TYPES else None

    _apply_content_type_hints(result, metadata)

    if metadata.get("file_name") and "file_name" not in result:
        result["file_name"] = str(metadata["file_name"])

    return result


def _apply_content_type_hints(result: dict, metadata: dict) -> None:
    hint = metadata.get("content_type_hint")
    asset_summary = metadata.get("asset_summary") or {}
    if hint == "mixed" or asset_summary.get("has_table") or asset_summary.get("has_image"):
        if result.get("content_type") == "text":
            result["content_type"] = "mixed"


def _enum_or_default(value: Any, field: str, default: str) -> str:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    allowed = _ENUM_SETS.get(field)
    if allowed is None or normalized in allowed:
        return normalized or default
    return default


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _business_line_codes_or_default(value: Any) -> list[str]:
    values = _as_str_list(value)
    normalized = [item for item in values if item in _BUSINESS_LINE_CODES]
    return normalized or list(_DEFAULT_BUSINESS_LINE_CODES)


def _taxonomy_codes(dimension: str) -> frozenset[str]:
    return frozenset(
        str(row["code"])
        for row in KNOWLEDGE_TAXONOMY_SEED_ROWS
        if row.get("dimension") == dimension and row.get("is_active", True)
    )


_BLOCK_TYPE_CODES = _taxonomy_codes("block_type")
_APPLICATION_TYPE_CODES = _taxonomy_codes("application_type")
_BUSINESS_LINE_CODES = _taxonomy_codes("business_line")

_ENUM_SETS: dict[str, frozenset[str]] = {
    "knowledge_type": _KNOWLEDGE_TYPES,
    "content_type": _CONTENT_TYPES,
    "status": _STATUSES,
    "security_level": _SECURITY_LEVELS,
    "review_status": _REVIEW_STATUSES,
    "block_type_code": _BLOCK_TYPE_CODES,
    "application_type_code": _APPLICATION_TYPE_CODES,
}
