from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是目录蓝图检索助手。将用户的自然语言搜索意图拆分为结构化 JSON。\n"
    "字段：semantic_query（用于向量语义检索，提炼核心概念）、"
    "keyword（用于关键词匹配，2-5个词）、"
    "product_tags、industry_tags、scenario_tags（数组，无则空数组）。\n"
    "只返回 JSON，不要 markdown。"
)


class SearchParseTimeoutError(Exception):
    pass


class SearchParseFailedError(Exception):
    pass


def parse_search_query_response(raw: str) -> dict[str, Any]:
    parsed = _parse_llm_json(raw)
    if parsed is None:
        raise SearchParseFailedError("invalid llm json")
    semantic_query = str(parsed.get("semantic_query") or "").strip()
    keyword = str(parsed.get("keyword") or "").strip()
    if not semantic_query and not keyword:
        raise SearchParseFailedError("semantic_query and keyword missing")
    return {
        "semantic_query": semantic_query,
        "keyword": keyword,
        "product_tags": _as_str_list(parsed.get("product_tags")),
        "industry_tags": _as_str_list(parsed.get("industry_tags")),
        "scenario_tags": _as_str_list(parsed.get("scenario_tags")),
    }


def parse_search_query(*, query: str) -> dict[str, Any]:
    if not settings.llm_enabled:
        raise SearchParseFailedError("llm not configured")
    text = query.strip()
    if not text:
        raise SearchParseFailedError("query empty")
    if len(text) > settings.blueprint_search_parse_query_max:
        raise SearchParseFailedError("query too long")
    raw = _chat_with_timeout(user_prompt=text)
    return parse_search_query_response(raw)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _chat_with_timeout(*, user_prompt: str) -> str:
    model = settings.blueprint_search_parse_model
    timeout_sec = settings.blueprint_search_parse_timeout_sec
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"])
    except TimeoutError as exc:
        raise SearchParseTimeoutError("search parse timed out") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise SearchParseTimeoutError("search parse timed out") from exc
        raise SearchParseFailedError("llm request failed") from exc
    except (urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise SearchParseFailedError("llm response malformed") from exc
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("blueprint search parse llm elapsed_ms=%.1f model=%s", elapsed_ms, model)


def _parse_llm_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
