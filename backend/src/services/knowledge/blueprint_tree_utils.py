from __future__ import annotations

import uuid
from typing import Any


def assign_node_codes(nodes: list[dict[str, Any]], *, prefix: str = "") -> None:
    for index, node in enumerate(nodes, start=1):
        code = f"{prefix}{index}" if not prefix else f"{prefix}.{index}"
        node["node_code"] = code
        children = node.get("children") or []
        assign_node_codes(children, prefix=code)


def flatten_tree(
    nested: list[dict[str, Any]], *, parent_temp_id: str | None = None
) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for node in nested:
        temp_id = str(uuid.uuid4())
        flat_node = {key: value for key, value in node.items() if key != "children"}
        flat_node["temp_id"] = temp_id
        flat_node["parent_temp_id"] = parent_temp_id
        flat.append(flat_node)
        children = node.get("children") or []
        flat.extend(flatten_tree(children, parent_temp_id=temp_id))
    return flat


def nest_tree(flat: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for node in flat:
        node_copy = {
            key: value for key, value in node.items() if key not in {"parent_temp_id", "temp_id"}
        }
        node_copy["children"] = []
        nodes_by_id[node["temp_id"]] = node_copy

    for node in flat:
        node_copy = nodes_by_id[node["temp_id"]]
        parent_temp_id = node.get("parent_temp_id")
        if parent_temp_id is None:
            roots.append(node_copy)
            continue
        parent = nodes_by_id.get(parent_temp_id)
        if parent is not None:
            parent["children"].append(node_copy)

    return roots


def map_llm_flags_to_importance(
    required_flag: bool | None, recommended_flag: bool | None
) -> str:
    if required_flag:
        return "required"
    if recommended_flag:
        return "recommended"
    return "optional"
