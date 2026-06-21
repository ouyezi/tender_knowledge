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
from src.services.llm_client import truncate_for_llm

logger = logging.getLogger(__name__)

_KNOWLEDGE_TYPES = frozenset({"fact", "template", "solution", "case", "table", "image"})
_CONTENT_TYPES = frozenset({"text", "mixed"})
_SOURCE_TYPES = frozenset(
    {"bid", "proposal", "qualification", "contract", "manual", "wiki", "case"}
)
_CATEGORIES = frozenset(
    {
        "qualification",
        "technical",
        "business",
        "legal",
        "personnel",
        "price",
        "case",
        "template",
    }
)
_STATUSES = frozenset({"draft", "active", "deprecated", "disabled"})
_SECURITY_LEVELS = frozenset({"public", "internal", "confidential"})
_REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})
_QUOTE_MODES = frozenset({"full", "partial"})
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

_SYSTEM_PROMPT = (
    "你是标书知识库属性预填助手。根据章节正文与元数据，输出 JSON 对象，字段包括："
    "title, summary, knowledge_type, content_type, source_type, category, status, "
    "security_level, review_status, quote_mode, template_type, tags, products, "
    "industries, customer_types, regions, issue_date, expire_date, is_template, "
    "winning_flag。"
    "industries/products/customer_types/regions/expire_date 可留空。"
    "只返回 JSON，不要解释。"
)

_DEFAULT_ENUMS: dict[str, str] = {
    "knowledge_type": "fact",
    "content_type": "text",
    "source_type": "bid",
    "category": "technical",
    "status": "draft",
    "security_level": "internal",
    "review_status": "approved",
    "quote_mode": "full",
}


def prefill_knowledge_attributes(*, content: str, metadata: dict) -> dict:
    """Prefill editable knowledge attributes from chapter content via LLM."""
    partial = _build_partial_result(metadata)
    if not settings.llm_enabled:
        partial["warnings"] = ["prefill_failed"]
        return partial

    try:
        raw = _chat_with_timeout(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(content, metadata),
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


def _build_user_prompt(content: str, metadata: dict) -> str:
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    return truncate_for_llm(f"元数据：{meta_json}\n\n章节正文：\n{content}")


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
        "title": "",
        "summary": None,
        "tags": [],
        "products": [],
        "industries": [],
        "customer_types": [],
        "regions": [],
        "issue_date": None,
        "expire_date": None,
        "is_template": False,
        "template_type": None,
        "winning_flag": False,
    }
    for key, default in _DEFAULT_ENUMS.items():
        result[key] = _enum_or_default(metadata.get(key), key, default)
    if metadata.get("file_name"):
        result["file_name"] = str(metadata["file_name"])
    if metadata.get("project_name"):
        result["project_name"] = str(metadata["project_name"])
    return result


def _normalize_prefill(parsed: dict, metadata: dict) -> dict:
    result = _build_partial_result(metadata)
    if parsed.get("title") is not None:
        result["title"] = str(parsed.get("title") or "")
    if parsed.get("summary") is not None:
        summary = parsed.get("summary")
        result["summary"] = str(summary) if summary else None

    for field in _DEFAULT_ENUMS:
        if field in parsed and parsed[field] is not None:
            result[field] = _enum_or_default(parsed.get(field), field, _DEFAULT_ENUMS[field])

    result["tags"] = _as_str_list(parsed.get("tags"))
    result["products"] = _as_str_list(parsed.get("products"))
    result["industries"] = _as_str_list(parsed.get("industries"))
    result["customer_types"] = _as_str_list(parsed.get("customer_types"))
    result["regions"] = _as_str_list(parsed.get("regions"))
    result["issue_date"] = parsed.get("issue_date")
    result["expire_date"] = parsed.get("expire_date")
    result["is_template"] = bool(parsed.get("is_template", result["is_template"]))
    result["winning_flag"] = bool(parsed.get("winning_flag", result["winning_flag"]))

    template_type = parsed.get("template_type")
    if template_type is not None:
        normalized = str(template_type).strip().lower()
        result["template_type"] = normalized if normalized in _TEMPLATE_TYPES else None

    if metadata.get("file_name") and "file_name" not in result:
        result["file_name"] = str(metadata["file_name"])
    if metadata.get("project_name") and "project_name" not in result:
        result["project_name"] = str(metadata["project_name"])

    return result


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


_ENUM_SETS: dict[str, frozenset[str]] = {
    "knowledge_type": _KNOWLEDGE_TYPES,
    "content_type": _CONTENT_TYPES,
    "source_type": _SOURCE_TYPES,
    "category": _CATEGORIES,
    "status": _STATUSES,
    "security_level": _SECURITY_LEVELS,
    "review_status": _REVIEW_STATUSES,
    "quote_mode": _QUOTE_MODES,
}
