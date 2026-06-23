from __future__ import annotations

import base64
import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

_VISION_SYSTEM_PROMPT = (
    "你是标书文档图片理解助手。分析图片并输出 JSON，字段："
    "caption（图片内容描述）、ocr_text（图中文字）、"
    "extracted_facts（结构化事实对象，可含 cert_name/issue_date/expire_date/confidence/"
    "information_role）。"
    "information_role 取值 core（核心信息，如证书/资质/合同关键页）或 auxiliary（辅助信息，如商品图/门店图/装饰图）。"
    "confidence 取值 high/medium/low。只返回 JSON，不要 markdown。"
)


def parse_vision_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("vision response must be object")
    return {
        "caption": str(payload.get("caption") or "").strip() or None,
        "ocr_text": str(payload.get("ocr_text") or "").strip() or None,
        "extracted_facts": payload.get("extracted_facts")
        if isinstance(payload.get("extracted_facts"), dict)
        else None,
    }


def is_core_image_extraction(extracted: dict[str, Any]) -> bool:
    facts = extracted.get("extracted_facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    role = facts.get("information_role") or facts.get("role")
    if role == "core":
        return True
    if role == "auxiliary":
        return False
    if facts.get("cert_name") or facts.get("issue_date") or facts.get("expire_date"):
        return True
    ocr = str(extracted.get("ocr_text") or "").strip()
    if len(ocr) >= 8:
        return True
    caption = str(extracted.get("caption") or "").strip()
    return bool(re.search(r"证书|许可|资质|认证|备案|证明|执照|ISO|GB/T", caption + ocr, re.I))


def extract_image(*, image_path: Path) -> dict[str, Any] | None:
    if not settings.llm_enabled or not image_path.is_file():
        return None

    mime = "image/png"
    suffix = image_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{encoded}"
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.knowledge_vision_model,
        "messages": [
            {"role": "system", "content": _VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请分析这张图片并返回 JSON。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
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
        with urllib.request.urlopen(request, timeout=settings.knowledge_vision_timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        raw = str(body["choices"][0]["message"]["content"])
        result = parse_vision_response(raw)
        logger.info(
            "vision extract ok path=%s elapsed_ms=%.1f",
            image_path.name,
            (time.perf_counter() - started) * 1000,
        )
        return result
    except (
        TimeoutError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            logger.warning("vision extract timeout path=%s", image_path)
        else:
            logger.warning("vision extract failed path=%s err=%s", image_path, exc)
        return None
