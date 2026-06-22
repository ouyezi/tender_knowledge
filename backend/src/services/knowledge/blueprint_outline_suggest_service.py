"""Stateless LLM outline suggestion from blueprint knowledge + user requirements."""

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
from src.services.knowledge.blueprint_field_utils import truncate_blueprint_field
from src.services.knowledge.blueprint_service import BlueprintNotFoundError, get_blueprint_detail

logger = logging.getLogger(__name__)

MAX_STRUCTURE_MD_CONTEXT = 800
MAX_NODE_TEXT_CONTEXT = 200
MAX_SUGGEST_DEPTH = 4

_SYSTEM_PROMPT = (
    "你是标书目录顾问。目录蓝图是已验证的推荐目录模板，参考权重最高。\n"
    "任务：以蓝图骨架为主，结合用户目录需求，输出有序目录建议 JSON。\n"
    "规则：\n"
    "1. 【骨架优先】以蓝图的 suggested_structure_md 与 nodes 树为主骨架："
    "保留其主要模块名称、层级顺序与拆分粒度；"
    "content_suggestion 应继承蓝图节点 cd/tr 要点，并按用户需求微调表述。\n"
    "2. 【审慎调整】默认不重组顶层模块、不合并蓝图已有子目录。"
    "仅当用户需求明确要求，或某蓝图模块对当前项目明显不适用时，才可增删改；"
    "须在 split_reason/no_split_reason 说明与蓝图的差异原因。\n"
    "3. 标题去掉原有序号前缀（如 1.、第一章）。\n"
    "4. 有 children 时填 split_reason，叶子节点填 no_split_reason，二者互斥。\n"
    "5. importance 优先沿用蓝图 imp，取值 required | recommended | optional。\n"
    "6. 只返回 JSON，不要 markdown 包裹。\n"
    "Schema：\n"
    '{"outline_title":"标题","summary":"整体说明","nodes":[{"title":"章节",'
    '"content_suggestion":"内容建议","importance":"required",'
    '"split_reason":"拆分理由或null","no_split_reason":"不拆分理由或null","children":[]}]}'
)


class OutlineSuggestValidationError(Exception):
    pass


class OutlineSuggestTimeoutError(Exception):
    pass


class OutlineSuggestFailedError(Exception):
    pass


def compact_blueprint_detail(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": detail.get("name") or "",
        "description": detail.get("description") or "",
        "source_chapter": detail.get("source_chapter_title") or "",
        "scenario_tags": detail.get("scenario_tags") or [],
        "product_tags": detail.get("product_tags") or [],
        "industry_tags": detail.get("industry_tags") or [],
        "suggested_structure_md": truncate_blueprint_field(
            detail.get("suggested_structure_md"),
            max_len=MAX_STRUCTURE_MD_CONTEXT,
        )
        or "",
        "nodes": [_compact_node(node) for node in detail.get("nodes") or []],
    }


def _compact_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "t": (node.get("node_title") or "").strip(),
        "imp": node.get("importance_level") or "optional",
        "cd": truncate_blueprint_field(node.get("content_description"), max_len=MAX_NODE_TEXT_CONTEXT) or "",
        "tr": truncate_blueprint_field(node.get("tender_response_hint"), max_len=MAX_NODE_TEXT_CONTEXT) or "",
        "children": [_compact_node(child) for child in node.get("children") or []],
    }


def build_suggest_user_prompt(*, blueprints: list[dict[str, Any]], requirement: str) -> str:
    payload = json.dumps(blueprints, ensure_ascii=False, separators=(",", ":"))
    return (
        "以下目录蓝图为推荐模板，请以其结构为主骨架生成建议目录。\n"
        "suggested_structure_md 描述建议模块组织；nodes 树含章节标题(t)、"
        "重要程度(imp)、内容要点(cd)、应标线索(tr)。\n"
        f"【目录蓝图经验】\n{payload}\n\n"
        f"【用户目录需求】\n{requirement.strip()}\n\n"
        "输出应与蓝图骨架高度一致：保留主要模块与层级；仅在必要时调整并说明理由。"
    )


def validate_suggest_nodes(nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(nodes, list) or not nodes:
        raise OutlineSuggestValidationError("nodes missing")
    return [validate_suggest_node(node, depth=1) for node in nodes]


def validate_suggest_node(node: Any, *, depth: int) -> dict[str, Any]:
    if depth > MAX_SUGGEST_DEPTH:
        raise OutlineSuggestValidationError("max depth exceeded")
    if not isinstance(node, dict):
        raise OutlineSuggestValidationError("node must be object")

    title = str(node.get("title") or "").strip()
    content_suggestion = str(node.get("content_suggestion") or "").strip()
    importance = str(node.get("importance") or node.get("imp") or "").strip()
    if not title or not content_suggestion:
        raise OutlineSuggestValidationError("title or content_suggestion missing")
    if importance not in {"required", "recommended", "optional"}:
        raise OutlineSuggestValidationError("invalid importance")

    children_raw = node.get("children") or []
    if not isinstance(children_raw, list):
        raise OutlineSuggestValidationError("children must be list")

    split_reason = _optional_text(node.get("split_reason"))
    no_split_reason = _optional_text(node.get("no_split_reason"))

    if children_raw:
        if not split_reason or no_split_reason:
            raise OutlineSuggestValidationError("parent must have split_reason only")
    else:
        if not no_split_reason or split_reason:
            raise OutlineSuggestValidationError("leaf must have no_split_reason only")

    children = [validate_suggest_node(child, depth=depth + 1) for child in children_raw]
    return {
        "title": title,
        "content_suggestion": content_suggestion,
        "importance": importance,
        "split_reason": split_reason,
        "no_split_reason": no_split_reason,
        "children": children,
    }


def suggest_outline(
    db: Session,
    *,
    kb_id: UUID,
    blueprint_ids: list[UUID],
    requirement_description: str,
) -> dict[str, Any]:
    if not settings.llm_enabled:
        raise OutlineSuggestFailedError("llm not configured")

    requirement = requirement_description.strip()
    if not requirement:
        raise OutlineSuggestFailedError("requirement_description empty")
    if len(requirement) > settings.blueprint_suggest_requirement_max:
        raise OutlineSuggestFailedError("requirement_description too long")
    if not blueprint_ids:
        raise OutlineSuggestFailedError("blueprint_ids empty")
    if len(blueprint_ids) > settings.blueprint_suggest_max_blueprints:
        raise OutlineSuggestFailedError("too many blueprint_ids")

    compact_contexts: list[dict[str, Any]] = []
    for blueprint_id in blueprint_ids:
        try:
            detail = get_blueprint_detail(db, kb_id=kb_id, blueprint_id=blueprint_id)
        except BlueprintNotFoundError:
            raise
        compact_contexts.append(compact_blueprint_detail(detail))

    user_prompt = build_suggest_user_prompt(blueprints=compact_contexts, requirement=requirement)
    raw = _chat_with_timeout(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    return parse_and_validate_llm_response(raw)


def parse_and_validate_llm_response(raw: str) -> dict[str, Any]:
    parsed = _parse_llm_json(raw)
    if parsed is None:
        raise OutlineSuggestFailedError("invalid llm json")

    outline_title = str(parsed.get("outline_title") or parsed.get("title") or "").strip()
    summary = str(parsed.get("summary") or parsed.get("desc") or "").strip()
    if not outline_title or not summary:
        raise OutlineSuggestFailedError("outline_title or summary missing")

    try:
        nodes = validate_suggest_nodes(parsed.get("nodes"))
    except OutlineSuggestValidationError as exc:
        raise OutlineSuggestFailedError(str(exc)) from exc

    return {
        "outline_title": outline_title,
        "summary": summary,
        "nodes": nodes,
    }


def _chat_with_timeout(*, system_prompt: str, user_prompt: str) -> str:
    model = settings.blueprint_suggest_model
    timeout_sec = settings.blueprint_suggest_timeout_sec
    max_tokens = settings.blueprint_suggest_max_tokens
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
        return str(body["choices"][0]["message"]["content"])
    except TimeoutError as exc:
        raise OutlineSuggestTimeoutError("outline suggest timed out") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise OutlineSuggestTimeoutError("outline suggest timed out") from exc
        raise OutlineSuggestFailedError("llm request failed") from exc
    except (urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise OutlineSuggestFailedError("llm response malformed") from exc
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("outline suggest llm elapsed_ms=%.1f model=%s", elapsed_ms, model)


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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
