from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.docx_content_collector import collect_content
from src.services.docx_hierarchy_inferrer import infer_hierarchy
from src.services.docx_tree_materializer import materialize_outline_nodes


@dataclass
class OutlineNode:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int
    needs_manual_review: bool = False


def _iter_paragraph_texts_from_fallback(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def parse_outline(path: str | Path) -> list[OutlineNode]:
    file_path = Path(path)
    try:
        collected = collect_content(file_path)
    except Exception:
        fallback_texts = _iter_paragraph_texts_from_fallback(file_path)
        return [
            OutlineNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=None,
                title=text,
                level=1,
                sort_order=idx,
                needs_manual_review=True,
            )
            for idx, text in enumerate(fallback_texts)
        ]

    inferred = infer_hierarchy(collected.blocks)
    return materialize_outline_nodes(inferred, collected.blocks)
