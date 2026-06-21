"""LLM blueprint draft generation from document heading subtree."""

from __future__ import annotations

import json
import re
import socket
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
from src.services.llm_client import truncate_for_llm

_SYSTEM_PROMPT = (
    "你是标书大纲蓝图助手。基于给定目录子树，输出 JSON 对象。"
    "顶层字段：outline_title, description, overall_strategy, usual_page_range, "
    "related_regulations, common_mistakes, template_style, nodes。"
    "nodes 为树结构，每个节点包含：node_title, node_level, purpose, writing_goal, "
    "writing_hint, required_flag, recommended_flag, content_type, keyword_hint, children。"
    "只返回 JSON，不要解释。"
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
    subtree = collect_subtree_outline(db, kb_id=kb_id, doc_id=doc_id, node_id=node_id)
    if not subtree.get("children"):
        raise NoChildNodesError

    raw = _chat_with_timeout(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(subtree),
    )
    parsed = _parse_llm_json(raw)
    if parsed is None:
        raise BlueprintGenerateFailedError("invalid llm json")

    llm_nodes = _normalize_nodes(parsed.get("nodes"))
    if not llm_nodes:
        raise BlueprintGenerateFailedError("llm nodes missing")
    assign_node_codes(llm_nodes)

    return {
        "name": str(parsed.get("outline_title") or subtree.get("node_title") or "").strip(),
        "description": _resolve_description(parsed),
        "source_doc_id": doc_id,
        "source_node_id": node_id,
        "source_chapter_title": subtree.get("node_title"),
        "related_regulations": _as_str_list(parsed.get("related_regulations")),
        "overall_strategy": _as_optional_text(parsed.get("overall_strategy")),
        "common_mistakes": _as_optional_text(parsed.get("common_mistakes")),
        "template_style": _as_optional_text(parsed.get("template_style")),
        "usual_page_range": _as_optional_text(parsed.get("usual_page_range")),
        "nodes": llm_nodes,
    }


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
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(
            DocumentTreeNode.sort_order.asc(),
            DocumentTreeNode.level.asc(),
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
        return {
            "node_title": node.title or "",
            "node_level": int(node.level or 1),
            "children": [build(child) for child in children_by_parent.get(node.node_id, [])],
        }

    return build(root)


def _chat_with_timeout(*, system_prompt: str, user_prompt: str) -> str:
    payload: dict[str, Any] = {
        "model": settings.blueprint_generate_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
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
            request, timeout=settings.blueprint_generate_timeout_sec
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"])
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise BlueprintGenerateTimeoutError("blueprint generation timed out") from exc
        raise BlueprintGenerateFailedError("llm request failed") from exc
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
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
    outline_json = json.dumps(subtree, ensure_ascii=False)
    return truncate_for_llm(f"目录子树：\n{outline_json}")


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
                "node_title": str(node.get("node_title") or "").strip(),
                "node_level": int(node.get("node_level") or 1),
                "node_order": index,
                "purpose": _as_optional_text(node.get("purpose")),
                "writing_goal": _as_optional_text(node.get("writing_goal")),
                "writing_hint": _as_optional_text(node.get("writing_hint")),
                "importance_level": map_llm_flags_to_importance(
                    _as_bool(node.get("required_flag")),
                    _as_bool(node.get("recommended_flag")),
                ),
                "content_type": _as_optional_text(node.get("content_type")),
                "keyword_hint": _as_str_list(node.get("keyword_hint")),
                "children": children,
            }
        )
    return normalized


def _resolve_description(parsed: dict[str, Any]) -> str | None:
    description = _as_optional_text(parsed.get("description"))
    if description:
        return description
    strategy = _as_optional_text(parsed.get("overall_strategy"))
    if not strategy:
        return None
    return truncate_for_llm(strategy, max_chars=120)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _as_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
