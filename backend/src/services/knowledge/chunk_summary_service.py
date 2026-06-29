from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any

from src.config import settings
from src.services.knowledge.certificate_field_utils import (
    earliest_expire_date_from_csv,
    normalize_certificate_date,
    normalize_certificate_number,
    parse_expire_date_value,
)

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "你是标书知识块摘要助手。输出 JSON：summary、certificate_number、certificate_date、"
    "expire_date、date_confidence（high/medium/low）。"
    "certificate_number/certificate_date 多个值用英文逗号分隔；expire_date 取最早失效日。"
    "图片信息中 information_role=core 的（如证书/资质）应写入 summary；"
    "information_role=auxiliary 的（如商品图/门店图）可忽略，不要写入 summary。"
    "只返回 JSON，不要 markdown。"
)


def apply_summary_update(
    *,
    current_summary: str | None,
    current_certificate_number: str | None,
    current_certificate_date: str | None,
    current_expire_date: date | None,
    llm_result: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    summary = str(llm_result.get("summary") or "").strip()
    if not summary:
        summary = current_summary or ""
        warnings.append("summary_rewrite_empty")

    fields: dict[str, Any] = {"summary": summary}
    date_confidence = str(llm_result.get("date_confidence") or "").strip().lower()
    if date_confidence == "high":
        cert_number = normalize_certificate_number(llm_result.get("certificate_number"))
        cert_date = normalize_certificate_date(llm_result.get("certificate_date"))
        expire_date = _parse_expire_date(llm_result.get("expire_date"))
        fields["certificate_number"] = cert_number if cert_number is not None else current_certificate_number
        fields["certificate_date"] = cert_date if cert_date is not None else current_certificate_date
        fields["expire_date"] = expire_date if expire_date is not None else current_expire_date
    else:
        fields["certificate_number"] = current_certificate_number
        fields["certificate_date"] = current_certificate_date
        fields["expire_date"] = current_expire_date

    return fields, warnings


def rewrite_chunk_summary(
    *,
    title: str,
    content: str,
    current_summary: str | None,
    image_context: str,
) -> dict[str, Any] | None:
    if not settings.llm_enabled:
        return None

    user_prompt = (
        f"标题：{title}\n"
        f"原摘要：{current_summary or ''}\n"
        f"正文：{content[:6000]}\n"
        f"图片信息：{image_context[:4000]}"
    )
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.knowledge_index_summary_model,
        "messages": [
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
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
        with urllib.request.urlopen(
            request, timeout=settings.knowledge_index_summary_timeout_sec
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        raw = str(body["choices"][0]["message"]["content"])
        parsed = _parse_llm_json(raw)
        if parsed is None:
            return None
        logger.info("chunk summary rewrite elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
        return parsed
    except (
        TimeoutError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
    ) as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            logger.warning("chunk summary rewrite timeout")
        else:
            logger.warning("chunk summary rewrite failed: %s", exc)
        return None


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


def _parse_expire_date(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return parse_expire_date_value(text)
