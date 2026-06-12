from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from docx import Document


_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[\.、]?\s+\S+")


@dataclass
class OutlineNode:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int
    needs_manual_review: bool = False


def _is_heading_style(style_name: str) -> tuple[bool, int]:
    lowered = (style_name or "").strip().lower()
    if not lowered.startswith("heading"):
        return False, 0
    parts = lowered.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return True, max(int(parts[-1]), 1)
    return True, 1


def _level_from_numbered_prefix(text: str) -> int | None:
    match = _NUMBERED_HEADING_RE.match(text)
    if not match:
        return None
    number_part = match.group(1).rstrip(".")
    return max(number_part.count(".") + 1, 1)


def _iter_paragraph_texts_from_fallback(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def parse_outline(path: str | Path) -> list[OutlineNode]:
    file_path = Path(path)
    heading_candidates: list[tuple[str, int]] = []
    all_paragraphs: list[str] = []

    try:
        doc = Document(str(file_path))
        for para in doc.paragraphs:
            text = (para.text or "").strip()
            if not text:
                continue
            all_paragraphs.append(text)

            is_heading, heading_level = _is_heading_style(getattr(para.style, "name", ""))
            if is_heading:
                heading_candidates.append((text, heading_level))
                continue

            numbered_level = _level_from_numbered_prefix(text)
            if numbered_level is not None:
                heading_candidates.append((text, numbered_level))
    except Exception:
        all_paragraphs = _iter_paragraph_texts_from_fallback(file_path)
        heading_candidates = []

    if not heading_candidates:
        return [
            OutlineNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=None,
                title=text,
                level=1,
                sort_order=idx,
                needs_manual_review=True,
            )
            for idx, text in enumerate(all_paragraphs)
        ]

    nodes: list[OutlineNode] = []
    last_seen_by_level: dict[int, str] = {}
    for idx, (title, level) in enumerate(heading_candidates):
        parent_temp_id = None
        if level > 1:
            for parent_level in range(level - 1, 0, -1):
                parent_temp_id = last_seen_by_level.get(parent_level)
                if parent_temp_id:
                    break
        temp_id = f"n{idx + 1}"
        node = OutlineNode(
            temp_id=temp_id,
            parent_temp_id=parent_temp_id,
            title=title,
            level=level,
            sort_order=idx,
            needs_manual_review=False,
        )
        nodes.append(node)
        last_seen_by_level[level] = temp_id

        for stale_level in list(last_seen_by_level.keys()):
            if stale_level > level:
                last_seen_by_level.pop(stale_level, None)
    return nodes
