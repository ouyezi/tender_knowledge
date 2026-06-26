from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.knowledge_chunk import KnowledgeChunk
from src.models.writing_technique import TechniqueStatus, WritingTechnique
from src.services.knowledge.writing_technique_field_utils import (
    APPLICABLE_SCENE_MAX,
    TITLE_MAX,
    WRITING_STRATEGY_MAX,
    WRITING_SUMMARY_MAX,
    clamp_confidence,
    coerce_usage_mode,
    truncate_technique_field,
)
from src.services.knowledge.writing_technique_prompt import SYSTEM_PROMPT
from src.services.knowledge.writing_technique_service import (
    TechniqueConflictError,
    apply_llm_payload,
    create_technique,
    get_technique_by_source,
)
from src.services.llm_client import truncate_for_llm

logger = logging.getLogger(__name__)


class TechniqueGenerateTimeoutError(Exception):
    pass


class TechniqueGenerateFailedError(Exception):
    pass


class TechniqueChunkNotFoundError(Exception):
    pass


def parse_llm_technique_payload(content: str) -> dict[str, Any]:
    data = _parse_llm_json(content)
    if data is None:
        raise TechniqueGenerateFailedError("invalid llm json")

    return {
        "title": truncate_technique_field(data.get("title"), max_len=TITLE_MAX) or "未命名撰写技巧",
        "applicable_scene": truncate_technique_field(
            data.get("applicable_scene"), max_len=APPLICABLE_SCENE_MAX
        )
        or "",
        "writing_summary": truncate_technique_field(
            data.get("writing_summary"), max_len=WRITING_SUMMARY_MAX
        )
        or "",
        "applicable_sections": _as_str_list(data.get("applicable_sections")),
        "tags": _as_str_list(data.get("tags")),
        "usage_mode": coerce_usage_mode(data.get("usage_mode")),
        "recommended_outline": _as_text(data.get("recommended_outline")),
        "writing_strategy": truncate_technique_field(
            data.get("writing_strategy"), max_len=WRITING_STRATEGY_MAX
        )
        or "",
        "must_include": _as_text(data.get("must_include")),
        "notes": _as_text(data.get("notes")),
        "output_requirement": _as_text(data.get("output_requirement")),
        "checklist": _as_text(data.get("checklist")),
        "confidence": clamp_confidence(data.get("score")),
    }


def generate_and_save_technique(
    db: Session,
    *,
    kb_id: UUID,
    chunk_id: int,
    confirm_overwrite: bool,
) -> WritingTechnique:
    chunk = (
        db.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.id == int(chunk_id),
            KnowledgeChunk.is_latest.is_(True),
        )
        .one_or_none()
    )
    if chunk is None:
        raise TechniqueChunkNotFoundError
    if not settings.llm_enabled:
        raise TechniqueGenerateFailedError("llm not configured")

    existing = get_technique_by_source(db, kb_id=kb_id, chunk_id=int(chunk_id))
    if existing is not None and not confirm_overwrite:
        raise TechniqueConflictError("source chunk already has a technique")

    user_prompt = _build_user_prompt(chunk_title=chunk.title, chunk_content=chunk.content)
    raw = _chat_with_timeout(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=2048)
    payload = parse_llm_technique_payload(raw)

    if existing is None:
        payload["source_chunk_id"] = int(chunk_id)
        payload["source_invalid"] = False
        row = create_technique(db, kb_id=kb_id, payload=payload)
    else:
        apply_llm_payload(existing, payload)
        existing.source_chunk_id = int(chunk_id)
        existing.source_invalid = False
        existing.status = TechniqueStatus.draft
        existing.version = int(existing.version) + 1
        row = existing

    db.flush()
    return row


def _build_user_prompt(*, chunk_title: str, chunk_content: str) -> str:
    return (
        "请从以下知识块中提炼可复用撰写技巧。\n\n"
        f"标题：{chunk_title.strip()}\n\n"
        f"正文：\n{truncate_for_llm(chunk_content or '')}"
    )


def _chat_with_timeout(*, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    model = settings.writing_technique_generate_model
    timeout_sec = settings.writing_technique_generate_timeout_sec
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
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
        content = str(body["choices"][0]["message"]["content"])
        logger.info(
            "writing technique llm ok model=%s elapsed_ms=%.1f content_chars=%d",
            model,
            (time.perf_counter() - started) * 1000,
            len(content),
        )
        return content
    except TimeoutError as exc:
        raise TechniqueGenerateTimeoutError("writing technique generation timed out") from exc
    except urllib.error.HTTPError as exc:
        raise TechniqueGenerateFailedError(f"llm http {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise TechniqueGenerateTimeoutError("writing technique generation timed out") from exc
        raise TechniqueGenerateFailedError("llm request failed") from exc
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise TechniqueGenerateFailedError("llm response malformed") from exc


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


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
