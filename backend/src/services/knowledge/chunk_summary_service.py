from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from src.config import settings
from src.services.knowledge.qualification_field_utils import (
    earliest_expire_date_from_qualification_info,
    normalize_qualification_info,
)

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "你是标书知识块摘要助手。输出 JSON：summary、qualification_info、date_confidence（high/medium/low）。"
    "qualification_info 格式：每条资质为 简称|编号|发证日期|有效期，多条用英文分号分隔；"
    "发证日期与有效期中的日期使用 YYYY-MM-DD；有效期可为长期有效等非日期文本。"
    "结合正文与图片信息提取或修正资质；information_role=core 的证书/资质图应写入 qualification_info；"
    "information_role=auxiliary 的图忽略。只返回 JSON，不要 markdown。"
)


def apply_summary_update(
    *,
    current_summary: str | None,
    current_qualification_info: str | None,
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
        normalized = normalize_qualification_info(llm_result.get("qualification_info"))
        fields["qualification_info"] = (
            normalized if normalized is not None else current_qualification_info
        )
        derived = earliest_expire_date_from_qualification_info(fields["qualification_info"])
        fields["expire_date"] = derived if derived is not None else current_expire_date
    else:
        fields["qualification_info"] = current_qualification_info
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
