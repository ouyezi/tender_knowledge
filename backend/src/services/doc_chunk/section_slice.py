from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.services.doc_chunk.linkage_validation import normalize_title, titles_compatible

_HEADING_RE = re.compile(r"^(#{1,8})[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
PREFACE_NODE_ID = "__preface__"
PREFACE_TITLE = "前言"


def is_preface_node_id(node_id: str | UUID) -> bool:
    return str(node_id) == PREFACE_NODE_ID


@dataclass(frozen=True, slots=True)
class OutlineSliceNode:
    node_id: str
    title: str
    level: int
    parent_id: str | None
    sort_order: int
    anchor_char_start: int | None = None


@dataclass(frozen=True, slots=True)
class _Heading:
    char_start: int
    level: int
    title: str


def outline_nodes_from_payload(payload: dict[str, Any]) -> list[OutlineSliceNode]:
    nodes: list[OutlineSliceNode] = []
    for raw in payload.get("nodes") or []:
        anchor = raw.get("anchor") or {}
        nodes.append(
            OutlineSliceNode(
                node_id=str(raw.get("node_id") or ""),
                title=str(raw.get("title") or ""),
                level=max(int(raw.get("level") or 1), 0),
                parent_id=str(raw["parent_id"]) if raw.get("parent_id") else None,
                sort_order=int(raw.get("sort_order") or 0),
                anchor_char_start=anchor.get("char_start"),
            )
        )
    return nodes


def outline_nodes_from_bid_nodes(nodes: list[Any]) -> list[OutlineSliceNode]:
    return [
        OutlineSliceNode(
            node_id=str(node.outline_node_id),
            title=str(node.title or ""),
            level=max(int(node.level or 1), 0),
            parent_id=str(node.parent_id) if node.parent_id else None,
            sort_order=int(node.sort_order or 0),
        )
        for node in nodes
    ]


def outline_nodes_from_tree_nodes(nodes: list[Any]) -> list[OutlineSliceNode]:
    return [
        OutlineSliceNode(
            node_id=str(node.node_id),
            title=str(node.title or ""),
            level=max(int(node.level or 1), 0),
            parent_id=str(node.parent_id) if getattr(node, "parent_id", None) else None,
            sort_order=int(node.sort_order or 0),
        )
        for node in nodes
    ]


def _parse_headings(content_md: str) -> list[_Heading]:
    return [
        _Heading(
            char_start=match.start(),
            level=len(match.group(1)),
            title=match.group(2).strip(),
        )
        for match in _HEADING_RE.finditer(content_md)
    ]


def _titles_match(node: OutlineSliceNode, heading: _Heading) -> bool:
    if node.level != heading.level:
        return False
    return titles_compatible(node.title, heading.title)


def _heading_matches_title(heading: _Heading, title: str, *, level: int | None = None) -> bool:
    if level is not None and heading.level != level:
        return False
    return titles_compatible(title, heading.title)


def _fallback_char_start(content_md: str, title: str, *, level: int | None = None) -> int | None:
    for heading in _parse_headings(content_md):
        if _heading_matches_title(heading, title, level=level):
            return heading.char_start
    if level is not None:
        for heading in _parse_headings(content_md):
            if _heading_matches_title(heading, title):
                return heading.char_start
    return None


def _build_node_heading_starts(nodes: list[OutlineSliceNode], content_md: str) -> dict[str, int]:
    headings = _parse_headings(content_md)
    ordered = sorted(nodes, key=lambda item: (item.sort_order, item.node_id))
    mapping: dict[str, int] = {}
    heading_idx = 0

    for node in ordered:
        matched = False
        while heading_idx < len(headings):
            heading = headings[heading_idx]
            if _titles_match(node, heading):
                mapping[node.node_id] = heading.char_start
                heading_idx += 1
                matched = True
                break
            heading_idx += 1
        if matched:
            continue

        fallback = _fallback_char_start(content_md, node.title, level=node.level)
        if fallback is None and node.anchor_char_start is not None:
            fallback = node.anchor_char_start
        if fallback is not None:
            mapping[node.node_id] = fallback

    return mapping


def _section_end_by_heading(content_md: str, start: int, level: int) -> int:
    for match in _HEADING_RE.finditer(content_md):
        if match.start() <= start:
            continue
        if len(match.group(1)) <= level:
            return match.start()
    return len(content_md)


def _descendant_node_ids(nodes: list[OutlineSliceNode], node_id: str) -> set[str]:
    by_parent: dict[str | None, list[str]] = {}
    for node in nodes:
        by_parent.setdefault(node.parent_id, []).append(node.node_id)
    result: set[str] = set()
    stack = list(by_parent.get(node_id, []))
    while stack:
        child_id = stack.pop()
        if child_id in result:
            continue
        result.add(child_id)
        stack.extend(by_parent.get(child_id, []))
    return result


def _section_end(
    content_md: str,
    nodes: list[OutlineSliceNode],
    node_map: dict[str, OutlineSliceNode],
    heading_starts: dict[str, int],
    node_id: str,
    start: int,
    level: int,
) -> int:
    end = _section_end_by_heading(content_md, start, level)
    descendant_ends: list[int] = []
    for desc_id in _descendant_node_ids(nodes, node_id):
        desc = node_map.get(desc_id)
        if desc is None:
            continue
        desc_start = heading_starts.get(desc_id)
        if desc_start is None:
            desc_start = _fallback_char_start(content_md, desc.title, level=desc.level)
        if desc_start is None:
            continue
        descendant_ends.append(_section_end_by_heading(content_md, desc_start, desc.level))
    if descendant_ends:
        end = min(end, max(descendant_ends))
    return end


def _preface_end(content_md: str, heading_starts: dict[str, int]) -> int:
    headings = _parse_headings(content_md)
    if headings:
        return headings[0].char_start
    if heading_starts:
        return min(heading_starts.values())
    return 0


def slice_section_markdown(
    content_md: str,
    nodes: list[OutlineSliceNode],
    node_id: str,
) -> str | None:
    if not content_md.strip() or not nodes:
        return None

    node_map = {node.node_id: node for node in nodes}
    heading_starts = _build_node_heading_starts(nodes, content_md)

    if node_id == PREFACE_NODE_ID:
        end = _preface_end(content_md, heading_starts)
        return content_md[:end]

    node = node_map.get(node_id)
    if node is None:
        return None

    start = heading_starts.get(node_id)
    if start is None:
        start = _fallback_char_start(content_md, node.title, level=node.level)
    if start is None:
        return None

    end = _section_end(content_md, nodes, node_map, heading_starts, node_id, start, node.level)
    return content_md[start:end]


def _is_descendant_of(
    node_id: str,
    ancestor_id: str,
    node_map: dict[str, OutlineSliceNode],
) -> bool:
    cursor = node_map.get(node_id)
    seen: set[str] = set()
    while cursor is not None and cursor.parent_id:
        if cursor.parent_id in seen:
            break
        if cursor.parent_id == ancestor_id:
            return True
        seen.add(cursor.parent_id)
        cursor = node_map.get(cursor.parent_id)
    return False


def _ordered_anchor_nodes(nodes: list[OutlineSliceNode]) -> list[OutlineSliceNode]:
    return sorted(
        nodes,
        key=lambda item: (
            item.anchor_char_start if item.anchor_char_start is not None else 10**9,
            item.sort_order,
            item.node_id,
        ),
    )


def _section_end_by_anchor(
    *,
    start: int,
    node_id: str,
    nodes: list[OutlineSliceNode],
    node_map: dict[str, OutlineSliceNode],
    content_len: int,
) -> int:
    for other in _ordered_anchor_nodes(nodes):
        other_start = other.anchor_char_start
        if other_start is None or other_start <= start:
            continue
        if _is_descendant_of(other.node_id, node_id, node_map):
            continue
        return other_start
    return content_len


def _preface_end_by_anchor(nodes: list[OutlineSliceNode]) -> int:
    starts = [node.anchor_char_start for node in nodes if node.anchor_char_start is not None]
    return min(starts) if starts else 0


def slice_section_by_anchor(
    content_md: str,
    outline_payload: dict[str, Any],
    outline_node_id: str,
) -> str | None:
    if not content_md.strip():
        return None
    nodes = outline_nodes_from_payload(outline_payload)
    if not nodes:
        return None
    node_map = {node.node_id: node for node in nodes}

    if outline_node_id == PREFACE_NODE_ID:
        end = _preface_end_by_anchor(nodes)
        return content_md[:end]

    node = node_map.get(outline_node_id)
    if node is None:
        return None
    start = node.anchor_char_start
    if start is None:
        return None
    end = _section_end_by_anchor(
        start=start,
        node_id=outline_node_id,
        nodes=nodes,
        node_map=node_map,
        content_len=len(content_md),
    )
    return content_md[start:end]


def slice_section_markdown_from_payload(
    content_md: str,
    outline_payload: dict[str, Any],
    outline_node_id: str,
) -> str | None:
    return slice_section_by_anchor(content_md, outline_payload, outline_node_id)
