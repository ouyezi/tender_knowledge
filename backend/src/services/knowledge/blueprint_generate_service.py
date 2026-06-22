"""LLM blueprint draft generation from document heading subtree."""

from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.document import Document, DocumentParseStatus
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.knowledge.blueprint_tree_utils import assign_node_codes, map_llm_flags_to_importance
from src.services.knowledge.blueprint_field_utils import (
    CONTENT_DESCRIPTION_MAX,
    CONTENT_SUMMARY_MAX,
    SUGGESTED_STRUCTURE_MD_MAX,
    TENDER_RESPONSE_HINT_MAX,
    truncate_blueprint_field,
)
from src.services.llm_client import truncate_for_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是标书目录蓝图专家。根据输入的目录子树（含 content_summary），输出指导后续标书编写的 JSON。\n"
    "规则：\n"
    "1. node_title 与 structure_md 中必须去掉原有序号前缀（如 1.、第一章），仅用 # 层级表达结构。\n"
    "2. desc、cd、tr 每项严格 1 句，禁止重复。\n"
    "3. 无应标线索时 tr 设为空字符串。\n"
    "4. imp 取值 required | recommended | optional。\n"
    "5. 只返回 JSON，不要 markdown 包裹或解释。\n"
    "Schema：\n"
    '{"title":"大纲标题","desc":"模块概要","structure_md":"建议目录 Markdown",'
    '"nodes":[{"t":"章节名","imp":"required","cd":"内容要点","tr":"应标线索","children":[]}]}'
)


class NoChildNodesError(Exception):
    pass


class BlueprintGenerateTimeoutError(Exception):
    pass


class BlueprintGenerateFailedError(Exception):
    pass


def generate_blueprint_draft(
    db: Session, *, kb_id: UUID, doc_id: UUID, node_id: UUID
) -> dict[str, Any]:
    if not settings.llm_enabled:
        raise BlueprintGenerateFailedError("llm not configured")

    started = time.perf_counter()
    logger.info(
        "blueprint generate start kb_id=%s doc_id=%s node_id=%s",
        kb_id,
        doc_id,
        node_id,
    )

    t0 = time.perf_counter()
    subtree = collect_subtree_outline(db, kb_id=kb_id, doc_id=doc_id, node_id=node_id)
    collect_ms = (time.perf_counter() - t0) * 1000
    subtree_node_count = _count_subtree_nodes(subtree)
    child_count = len(subtree.get("children") or [])

    if not subtree.get("children"):
        logger.info(
            "blueprint generate rejected: no child nodes kb_id=%s node_id=%s (%.1fms)",
            kb_id,
            node_id,
            collect_ms,
        )
        raise NoChildNodesError

    user_prompt = _build_user_prompt(subtree)
    max_tokens = _estimate_max_tokens(subtree_node_count=subtree_node_count)
    logger.info(
        "blueprint generate prepared title=%r subtree_nodes=%d direct_children=%d "
        "prompt_chars=%d max_tokens=%d collect_ms=%.1f",
        subtree.get("node_title"),
        subtree_node_count,
        child_count,
        len(user_prompt),
        max_tokens,
        collect_ms,
    )

    t1 = time.perf_counter()
    raw = _chat_with_timeout(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
    )
    llm_ms = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    parsed = _parse_llm_json(raw)
    if parsed is None:
        logger.warning(
            "blueprint generate invalid json kb_id=%s node_id=%s llm_ms=%.1f raw_len=%d",
            kb_id,
            node_id,
            llm_ms,
            len(raw),
        )
        raise BlueprintGenerateFailedError("invalid llm json")

    llm_nodes = _normalize_nodes(parsed.get("nodes"))
    if not llm_nodes:
        raise BlueprintGenerateFailedError("llm nodes missing")
    wrapped_nodes = _wrap_nodes_with_source_root(
        source_title=str(subtree.get("node_title") or ""),
        llm_nodes=llm_nodes,
    )
    assign_node_codes(wrapped_nodes)
    parse_ms = (time.perf_counter() - t2) * 1000

    total_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "blueprint generate done kb_id=%s node_id=%s output_nodes=%d "
        "llm_ms=%.1f parse_ms=%.1f total_ms=%.1f",
        kb_id,
        node_id,
        _count_subtree_nodes({"children": llm_nodes}),
        llm_ms,
        parse_ms,
        total_ms,
    )

    return {
        "name": _resolve_title(parsed, fallback=str(subtree.get("node_title") or "")),
        "description": _resolve_description(parsed),
        "source_doc_id": str(doc_id),
        "source_node_id": str(node_id),
        "source_chapter_title": subtree.get("node_title"),
        "suggested_structure_md": truncate_blueprint_field(
            _as_optional_text(
                parsed.get("suggested_structure_md")
                or parsed.get("structure_md")
            ),
            max_len=SUGGESTED_STRUCTURE_MD_MAX,
        ),
        "nodes": wrapped_nodes,
    }


def aggregate_content_summary(
    nodes: list[DocumentTreeNode],
    *,
    root_id: UUID,
) -> str:
    """Collect non-heading content_preview under a heading subtree."""
    children_by_parent: dict[UUID | None, list[DocumentTreeNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    parts: list[str] = []

    def walk(node_id: UUID) -> None:
        for child in sorted(children_by_parent.get(node_id, []), key=lambda item: item.sort_order):
            if child.node_type != DocumentTreeNodeType.heading:
                preview = (child.content_preview or "").strip()
                if preview:
                    parts.append(preview)
            else:
                walk(child.node_id)

    walk(root_id)
    joined = "\n".join(parts).strip()
    return truncate_blueprint_field(joined, max_len=CONTENT_SUMMARY_MAX) or ""


def collect_subtree_outline(
    db: Session, *, kb_id: UUID, doc_id: UUID, node_id: UUID
) -> dict[str, Any]:
    ready_document = (
        db.query(Document)
        .filter(
            Document.kb_id == kb_id,
            Document.document_id == doc_id,
            Document.parse_status == DocumentParseStatus.ready,
        )
        .one_or_none()
    )
    if ready_document is None:
        raise BlueprintGenerateFailedError("document not ready")

    nodes = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == doc_id,
        )
        .order_by(
            DocumentTreeNode.sort_order.asc(),
            DocumentTreeNode.level.asc().nulls_last(),
            DocumentTreeNode.created_at.asc(),
        )
        .all()
    )
    by_id = {node.node_id: node for node in nodes}
    root = by_id.get(node_id)
    if root is None:
        raise BlueprintGenerateFailedError("node not found")

    children_by_parent: dict[UUID | None, list[DocumentTreeNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    def build(node: DocumentTreeNode) -> dict[str, Any]:
        child_headings = [
            child
            for child in children_by_parent.get(node.node_id, [])
            if child.node_type == DocumentTreeNodeType.heading
        ]
        return {
            "node_title": node.title or "",
            "node_level": int(node.level or 1),
            "content_summary": aggregate_content_summary(nodes, root_id=node.node_id),
            "children": [build(child) for child in child_headings],
        }

    return build(root)


def _estimate_max_tokens(*, subtree_node_count: int) -> int:
    """Scale output budget with subtree size; cap at blueprint_generate_max_tokens."""
    per_node = 220
    base = 384
    estimated = base + subtree_node_count * per_node
    return min(settings.blueprint_generate_max_tokens, max(1024, estimated))


def _count_subtree_nodes(subtree: dict[str, Any]) -> int:
    children = subtree.get("children") or []
    return 1 + sum(_count_subtree_nodes(child) for child in children)


def _chat_with_timeout(*, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    model = settings.blueprint_generate_model
    timeout_sec = settings.blueprint_generate_timeout_sec
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
    logger.info(
        "blueprint llm request model=%s timeout_sec=%s max_tokens=%d "
        "system_chars=%d user_chars=%d url=%s",
        model,
        timeout_sec,
        max_tokens,
        len(system_prompt),
        len(user_prompt),
        url,
    )

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
        elapsed_ms = (time.perf_counter() - started) * 1000
        usage = body.get("usage") or {}
        content = str(body["choices"][0]["message"]["content"])
        logger.info(
            "blueprint llm response ok elapsed_ms=%.1f content_chars=%d "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            elapsed_ms,
            len(content),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
        return content
    except TimeoutError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.warning(
            "blueprint llm timeout elapsed_ms=%.1f timeout_sec=%s model=%s",
            elapsed_ms,
            timeout_sec,
            model,
        )
        raise BlueprintGenerateTimeoutError("blueprint generation timed out") from exc
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "blueprint llm http error status=%s elapsed_ms=%.1f model=%s body=%s",
            exc.code,
            elapsed_ms,
            model,
            err_body[:800],
        )
        raise BlueprintGenerateFailedError(f"llm http {exc.code}") from exc
    except urllib.error.URLError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            logger.warning(
                "blueprint llm timeout (urlerror) elapsed_ms=%.1f timeout_sec=%s model=%s",
                elapsed_ms,
                timeout_sec,
                model,
            )
            raise BlueprintGenerateTimeoutError("blueprint generation timed out") from exc
        logger.error(
            "blueprint llm url error elapsed_ms=%.1f model=%s reason=%s",
            elapsed_ms,
            model,
            reason or exc,
        )
        raise BlueprintGenerateFailedError("llm request failed") from exc
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.error(
            "blueprint llm malformed response elapsed_ms=%.1f model=%s err=%s",
            elapsed_ms,
            model,
            exc,
        )
        raise BlueprintGenerateFailedError("llm response malformed") from exc


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


def _build_user_prompt(subtree: dict[str, Any]) -> str:
    outline_json = json.dumps(subtree, ensure_ascii=False, separators=(",", ":"))
    return truncate_for_llm(f"目录子树（含 content_summary）：\n{outline_json}")


def _wrap_nodes_with_source_root(
    *,
    source_title: str,
    llm_nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use source chapter as blueprint level-1 root; LLM nodes become its descendants."""
    title = source_title.strip()
    content_nodes = llm_nodes
    root_fields: dict[str, Any] = {
        "content_description": None,
        "tender_response_hint": None,
        "importance_level": "required",
    }

    if len(llm_nodes) == 1 and (llm_nodes[0].get("node_title") or "").strip() == title:
        matched = llm_nodes[0]
        root_fields = {
            "content_description": matched.get("content_description"),
            "tender_response_hint": matched.get("tender_response_hint"),
            "importance_level": matched.get("importance_level") or "required",
        }
        content_nodes = matched.get("children") or []

    def remap_levels(nodes: list[dict[str, Any]], level: int) -> list[dict[str, Any]]:
        remapped: list[dict[str, Any]] = []
        for index, node in enumerate(nodes, start=1):
            remapped.append(
                {
                    **node,
                    "node_level": level,
                    "node_order": index,
                    "children": remap_levels(node.get("children") or [], level + 1),
                }
            )
        return remapped

    return [
        {
            "node_title": title,
            "node_level": 1,
            "node_order": 1,
            **root_fields,
            "children": remap_levels(content_nodes, level=2),
        }
    ]


def _normalize_nodes(raw_nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, node in enumerate(raw_nodes, start=1):
        if not isinstance(node, dict):
            continue
        children = _normalize_nodes(node.get("children"))
        normalized.append(
            {
                "node_title": _node_title(node),
                "node_level": int(node.get("node_level") or 1),
                "node_order": index,
                "content_description": truncate_blueprint_field(
                    _node_text(node, "content_description", "cd"),
                    max_len=CONTENT_DESCRIPTION_MAX,
                ),
                "tender_response_hint": truncate_blueprint_field(
                    _node_text(node, "tender_response_hint", "tr"),
                    max_len=TENDER_RESPONSE_HINT_MAX,
                ),
                "importance_level": _resolve_importance_level(node),
                "children": children,
            }
        )
    return normalized


def _resolve_description(parsed: dict[str, Any]) -> str | None:
    return _as_optional_text(parsed.get("description") or parsed.get("desc"))


def _resolve_title(parsed: dict[str, Any], *, fallback: str) -> str:
    return str(
        parsed.get("outline_title") or parsed.get("title") or fallback or ""
    ).strip()


def _node_title(node: dict[str, Any]) -> str:
    return str(node.get("node_title") or node.get("t") or "").strip()


def _node_text(node: dict[str, Any], long_key: str, short_key: str) -> str | None:
    return _as_optional_text(node.get(long_key) or node.get(short_key))


def _resolve_importance_level(node: dict[str, Any]) -> str:
    raw = node.get("importance_level") or node.get("importance") or node.get("imp")
    if isinstance(raw, str) and raw.strip() in {"required", "recommended", "optional"}:
        return raw.strip()
    return map_llm_flags_to_importance(
        _as_bool(node.get("required_flag")),
        _as_bool(node.get("recommended_flag")),
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
