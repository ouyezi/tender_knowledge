from __future__ import annotations

import re
from typing import Any

_SECTION_NO_RE = re.compile(r"^(\d+(?:\.\d+)*)")


def parse_section_no(title: str) -> str | None:
    text = (title or "").strip()
    match = _SECTION_NO_RE.match(text)
    if not match:
        return None
    return match.group(1)


def _level_from_section_no(section_no: str) -> int:
    return min(max(section_no.count(".") + 1, 1), 8)


def infer_structure_from_section_numbers(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(nodes, key=lambda n: int(n.get("sort_order") or 0))
    section_to_id: dict[str, str] = {}
    patches: list[dict[str, Any]] = []

    for node in ordered:
        node_id = str(node.get("node_id") or "").strip()
        if not node_id:
            continue
        section_no = parse_section_no(str(node.get("title") or ""))
        if not section_no:
            continue
        level = _level_from_section_no(section_no)
        parent_id = None
        if "." in section_no:
            parent_section = section_no.rsplit(".", 1)[0]
            parent_id = section_to_id.get(parent_section)
        patches.append({"node_id": node_id, "level": level, "parent_id": parent_id})
        section_to_id[section_no] = node_id

    return patches
