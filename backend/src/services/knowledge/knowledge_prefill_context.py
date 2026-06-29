"""Build enriched context for knowledge entry prefill."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document import Document
from src.services.knowledge.entry_content_service import (
    ContentNotAvailableError,
    DocumentNotFoundError,
    NodeNotFoundError,
    build_catalog_path,
    get_node_preview,
    knowledge_source_type_for_document,
)
from src.services.llm_client import truncate_for_llm


def format_catalog_breadcrumb(catalog_path: list[dict[str, Any]] | None) -> str:
    if not catalog_path:
        return ""
    titles = [str(item.get("title") or "").strip() for item in catalog_path if item.get("title")]
    return " > ".join(title for title in titles if title)


def summarize_assets(assets: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not assets:
        return {"total": 0, "by_type": {}, "has_table": False, "has_image": False}
    by_type: dict[str, int] = defaultdict(int)
    for asset in assets:
        asset_type = str(asset.get("asset_type") or "unknown")
        by_type[asset_type] += 1
    return {
        "total": len(assets),
        "by_type": dict(by_type),
        "has_table": by_type.get("table", 0) > 0,
        "has_image": by_type.get("image", 0) > 0,
    }


def enrich_prefill_metadata(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    node_id: UUID,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    enriched: dict[str, Any] = dict(metadata or {})

    document = (
        db.query(Document)
        .filter(Document.kb_id == kb_id, Document.document_id == doc_id)
        .one_or_none()
    )
    if document is not None:
        enriched.setdefault("file_name", document.document_name)
        enriched.setdefault("source_type", knowledge_source_type_for_document(document))

    has_catalog = bool(enriched.get("catalog_path"))
    has_chapter = bool(enriched.get("chapter_title"))

    if has_catalog and has_chapter and enriched.get("asset_summary") is not None:
        enriched["catalog_breadcrumb"] = format_catalog_breadcrumb(enriched.get("catalog_path"))
        return enriched

    try:
        preview = get_node_preview(db, kb_id=kb_id, doc_id=doc_id, node_id=node_id)
        enriched.setdefault("chapter_title", preview.get("title"))
        enriched.setdefault("catalog_path", preview.get("catalog_path"))
        enriched.setdefault("content_type_hint", preview.get("content_type"))
        if enriched.get("asset_summary") is None:
            enriched["asset_summary"] = summarize_assets(preview.get("assets"))
    except (DocumentNotFoundError, NodeNotFoundError, ContentNotAvailableError):
        if not has_catalog:
            nodes = _load_heading_nodes_light(db, kb_id=kb_id, doc_id=doc_id)
            nodes_by_id = {node.node_id: node for node in nodes}
            if node_id in nodes_by_id:
                enriched.setdefault("chapter_title", nodes_by_id[node_id].title or "")
                enriched.setdefault("catalog_path", build_catalog_path(nodes_by_id, node_id))

    enriched["catalog_breadcrumb"] = format_catalog_breadcrumb(enriched.get("catalog_path"))
    return enriched


def build_user_prompt(*, content: str, context: dict[str, Any]) -> str:
    context_payload = {
        "file_name": context.get("file_name"),
        "source_type": context.get("source_type"),
        "project_name": context.get("project_name"),
        "chapter_title": context.get("chapter_title"),
        "catalog_breadcrumb": context.get("catalog_breadcrumb"),
        "catalog_path": context.get("catalog_path"),
        "content_type_hint": context.get("content_type_hint"),
        "asset_summary": context.get("asset_summary"),
    }
    context_json = json_dumps(context_payload)
    body = (
        f"【录入上下文】\n{context_json}\n\n"
        f"【章节正文】\n{content.strip()}\n\n"
        "请根据上下文与正文输出 JSON。"
    )
    return truncate_for_llm(body)


def json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _load_heading_nodes_light(db: Session, *, kb_id: UUID, doc_id: UUID):
    from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType

    return (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == doc_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .all()
    )
