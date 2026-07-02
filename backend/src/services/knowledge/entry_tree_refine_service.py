from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.document import Document, DocumentParseStatus
from src.services.doc_chunk.outline_heading_correction import (
    apply_outline_heading_corrections,
    infer_outline_node_map_from_headings,
)
from src.services.doc_chunk.outline_store import load_outline, load_outline_node_map, persist_outline
from src.services.doc_chunk.repair_document_tree_headings import repair_document_tree_headings
from src.services.knowledge.entry_content_service import DocumentNotFoundError
from src.services.knowledge.entry_tree_section_utils import (
    infer_structure_from_section_numbers,
    parse_section_no,
)
from src.services.llm_client import chat_completion, is_llm_available, truncate_for_llm

logger = logging.getLogger(__name__)

_MAX_OUTLINE_NODES = 500
_MAX_LLM_USER_PROMPT_CHARS = 60_000

_SYSTEM_PROMPT = (
    "你是标书目录层级优化助手。仅优化无章节号节点的目录层级。\n"
    "输入字段：\n"
    "  numbered_context: 已有章节号节点 [[i,sn,t,l,p,s],...]，sn=章节号，供理解树形\n"
    "  targets: 待优化节点 [[i,t,l,p,s],...]\n"
    "  i=node_id（不可改） t=title（不可改） l=level(1-8) p=parent_id(null或已有i) s=sort_order\n"
    "规则：\n"
    "1) 不得修改任何标题 t\n"
    "2) 不得增删 i\n"
    "3) p 必须为 null 或输入中已有的 i\n"
    "4) 仅调整 targets 中节点的 l/p/s\n"
    "只返回 JSON："
    '{"changes":[[i,null,l,p,s],...],"summary":"一句变更说明"}\n'
    "changes 中第二项 t 必须为 null；仅包含需修改的 targets 节点。"
)

_DEFAULT_INSTRUCTION = "为无章节号节点推断合理的 level/parent_id/sort_order，不得修改标题。"


class EntryTreeRefineError(Exception):
    pass


class EntryTreeRefineUnavailableError(EntryTreeRefineError):
    pass


def _normalize_parent_id(parent_id: Any, *, known_node_ids: set[str]) -> str | None:
    if parent_id is None:
        return None
    parent_key = str(parent_id).strip()
    if not parent_key or parent_key not in known_node_ids:
        return None
    return parent_key


def _outline_nodes(outline_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in (outline_payload.get("nodes") or []) if isinstance(node, dict)]


def _partition_nodes_by_section_no(
    nodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    numbered: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for node in nodes:
        if parse_section_no(str(node.get("title") or "")):
            numbered.append(node)
        else:
            targets.append(node)
    return numbered, targets


def _numbered_context_row(node: dict[str, Any]) -> list[Any]:
    parent_id = node.get("parent_id")
    return [
        str(node.get("node_id") or ""),
        parse_section_no(str(node.get("title") or "")) or "",
        str(node.get("title") or ""),
        int(node.get("level") or 1),
        str(parent_id).strip() if parent_id else None,
        int(node.get("sort_order") or 0),
    ]


def _target_row(node: dict[str, Any]) -> list[Any]:
    parent_id = node.get("parent_id")
    return [
        str(node.get("node_id") or ""),
        str(node.get("title") or ""),
        int(node.get("level") or 1),
        str(parent_id).strip() if parent_id else None,
        int(node.get("sort_order") or 0),
    ]


def _batch_nodes(nodes: list[dict[str, Any]], *, batch_size: int) -> list[list[dict[str, Any]]]:
    if batch_size <= 0:
        return [nodes]
    return [nodes[index : index + batch_size] for index in range(0, len(nodes), batch_size)]


def _compact_change_to_patch(
    change: list[Any],
    *,
    known_node_ids: set[str],
    base_nodes: dict[str, dict[str, Any]],
    structure_only: bool = True,
) -> dict[str, Any] | None:
    if not isinstance(change, list) or len(change) < 1:
        return None
    node_id = str(change[0] or "").strip()
    if not node_id or node_id not in known_node_ids:
        return None
    base = base_nodes.get(node_id) or {}
    title = str(base.get("title") or "").strip()
    if not title:
        return None

    level_raw = change[2] if len(change) > 2 else None
    parent_raw = change[3] if len(change) > 3 else None
    sort_raw = change[4] if len(change) > 4 else None

    level = max(int(level_raw if level_raw is not None else base.get("level") or 1), 1)
    if parent_raw is None:
        parent_id = base.get("parent_id")
        parent_key = str(parent_id).strip() if parent_id else None
    else:
        parent_key = _normalize_parent_id(parent_raw, known_node_ids=known_node_ids)
    sort_order = int(sort_raw if sort_raw is not None else base.get("sort_order") or 0)

    patch: dict[str, Any] = {
        "node_id": node_id,
        "level": level,
        "parent_id": parent_key,
        "sort_order": sort_order,
    }
    if not structure_only:
        title_raw = change[1] if len(change) > 1 else None
        if title_raw is not None:
            patch["title"] = str(title_raw).strip() or title
        else:
            patch["title"] = title
    return patch


def _extract_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise EntryTreeRefineError("LLM 返回格式无效")
    return payload


def _parse_llm_outline_response(
    raw: str,
    *,
    known_node_ids: set[str],
    base_nodes: dict[str, dict[str, Any]] | None = None,
    structure_only: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    payload = _extract_json_payload(raw)
    summary = str(payload.get("summary") or payload.get("change_summary") or "目录已优化").strip()
    base = base_nodes or {}

    changes = payload.get("changes")
    if not isinstance(changes, list):
        raise EntryTreeRefineError("LLM 未返回 changes")

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for change in changes:
        if not isinstance(change, list):
            continue
        patch = _compact_change_to_patch(
            change,
            known_node_ids=known_node_ids,
            base_nodes=base,
            structure_only=structure_only,
        )
        if patch is None:
            continue
        node_id = patch["node_id"]
        if node_id in seen:
            continue
        validated.append(patch)
        seen.add(node_id)
    return validated, summary


def _build_base_nodes(outline_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base: dict[str, dict[str, Any]] = {}
    for node in _outline_nodes(outline_payload):
        node_id = str(node.get("node_id") or "").strip()
        if node_id:
            base[node_id] = node
    return base


def _merge_outline_nodes(
    outline_payload: dict[str, Any],
    refined_nodes: list[dict[str, Any]],
    *,
    preserve_titles: bool = True,
) -> dict[str, Any]:
    refined_by_id = {node["node_id"]: node for node in refined_nodes}
    merged_nodes: list[dict[str, Any]] = []
    for node in _outline_nodes(outline_payload):
        node_id = str(node.get("node_id") or "")
        patch = refined_by_id.get(node_id)
        if patch:
            if preserve_titles:
                patch = {key: value for key, value in patch.items() if key != "title"}
            merged_nodes.append({**node, **patch})
        else:
            merged_nodes.append(node)
    return {**outline_payload, "nodes": merged_nodes}


def _build_pass2_user_prompt(
    *,
    instruction: str,
    numbered_nodes: list[dict[str, Any]],
    target_nodes: list[dict[str, Any]],
) -> str:
    payload = {
        "instruction": instruction,
        "numbered_context": [_numbered_context_row(node) for node in numbered_nodes],
        "targets": [_target_row(node) for node in target_nodes],
    }
    return json.dumps(payload, ensure_ascii=False)


def refine_entry_document_tree(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    instruction: str | None = None,
) -> dict[str, Any]:
    document = (
        db.query(Document)
        .filter(
            Document.kb_id == kb_id,
            Document.document_id == doc_id,
            Document.parse_status == DocumentParseStatus.ready,
        )
        .one_or_none()
    )
    if document is None:
        raise DocumentNotFoundError

    repaired = repair_document_tree_headings(db, document_id=doc_id)
    outline_payload = load_outline(document_id=doc_id)
    if not outline_payload:
        raise EntryTreeRefineError("文档 outline 不可用，请重新解析后再试")

    outline_map = load_outline_node_map(document_id=doc_id)
    if not outline_map:
        from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType

        headings = (
            db.query(DocumentTreeNode)
            .filter(
                DocumentTreeNode.document_id == doc_id,
                DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
            )
            .all()
        )
        outline_map = infer_outline_node_map_from_headings(outline_payload, headings)

    llm_updated = 0
    change_summary = "已执行目录修复"
    engine = "repair"
    instruction_text = (instruction or _DEFAULT_INSTRUCTION).strip()

    nodes = _outline_nodes(outline_payload)[:_MAX_OUTLINE_NODES]
    deterministic_patches = infer_structure_from_section_numbers(nodes)
    deterministic_applied = bool(deterministic_patches)
    if deterministic_applied:
        outline_payload = _merge_outline_nodes(
            outline_payload,
            deterministic_patches,
            preserve_titles=True,
        )

    numbered_nodes, target_nodes = _partition_nodes_by_section_no(_outline_nodes(outline_payload))
    base_nodes = _build_base_nodes(outline_payload)
    known_ids = set(base_nodes.keys())
    llm_applied = False
    llm_summaries: list[str] = []

    if target_nodes and is_llm_available() and outline_map:
        target_batches = _batch_nodes(
            target_nodes,
            batch_size=settings.entry_tree_refine_batch_size,
        )
        try:
            llm_patches: list[dict[str, Any]] = []
            for batch_index, batch_targets in enumerate(target_batches, start=1):
                user_prompt = truncate_for_llm(
                    _build_pass2_user_prompt(
                        instruction=instruction_text,
                        numbered_nodes=numbered_nodes,
                        target_nodes=batch_targets,
                    ),
                    max_chars=_MAX_LLM_USER_PROMPT_CHARS,
                )
                logger.info(
                    "entry tree LLM refine batch document_id=%s batch=%s/%s targets=%s model=%s",
                    doc_id,
                    batch_index,
                    len(target_batches),
                    len(batch_targets),
                    settings.entry_tree_refine_model,
                )
                response = chat_completion(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.1,
                    max_tokens=settings.entry_tree_refine_max_tokens,
                    timeout_sec=settings.entry_tree_refine_timeout_sec,
                    model=settings.entry_tree_refine_model,
                    enable_thinking=False,
                )
                if response is None:
                    raise EntryTreeRefineError(
                        f"第 {batch_index}/{len(target_batches)} 批 LLM 调用失败或超时"
                    )
                batch_patches, batch_summary = _parse_llm_outline_response(
                    response.content,
                    known_node_ids=known_ids,
                    base_nodes=base_nodes,
                    structure_only=True,
                )
                llm_patches.extend(batch_patches)
                if batch_summary:
                    llm_summaries.append(batch_summary)

            if llm_patches:
                outline_payload = _merge_outline_nodes(
                    outline_payload,
                    llm_patches,
                    preserve_titles=True,
                )
                llm_applied = True
        except EntryTreeRefineError as exc:
            logger.warning("entry tree LLM refine skipped document_id=%s: %s", doc_id, exc)
            if not deterministic_applied:
                change_summary = f"已执行目录修复（LLM 结果无法应用：{exc}）"
    elif target_nodes and not is_llm_available():
        if not deterministic_applied:
            change_summary = "已执行目录修复（大模型未配置，未应用 LLM 优化）"

    if deterministic_applied or llm_applied:
        persist_outline(document_id=doc_id, outline_payload=outline_payload)
        llm_updated = apply_outline_heading_corrections(
            db,
            document_id=doc_id,
            outline_payload=outline_payload,
            outline_node_to_tree_id=outline_map,
        )
        if llm_applied and deterministic_applied:
            engine = "hybrid"
            change_summary = "；".join(
                ["已按章节号规则优化目录层级", *dict.fromkeys(llm_summaries)]
            )
        elif llm_applied:
            engine = "llm"
            change_summary = "；".join(dict.fromkeys(llm_summaries)) or "目录已优化"
        else:
            engine = "deterministic"
            change_summary = "已按章节号规则优化目录层级"

    db.commit()
    return {
        "repaired_nodes": repaired,
        "llm_updated_nodes": llm_updated,
        "change_summary": change_summary,
        "engine": engine,
    }
