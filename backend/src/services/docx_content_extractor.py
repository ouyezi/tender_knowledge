from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from docx import Document

from src.services.docx_outline_parser import OutlineNode
from src.services.variable_detector import detect_variables

_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[\.、]?\s+\S+")


def _is_heading(style_name: str, text: str) -> bool:
    lowered = (style_name or "").strip().lower()
    if lowered.startswith("heading"):
        return True
    return _NUMBERED_HEADING_RE.match(text) is not None


def extract_fixed_paragraph_materials(
    path: str | Path,
    *,
    outline_nodes: list[OutlineNode] | None = None,
) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    file_path = Path(path)
    chapter_index = 0
    current_chapter_temp_id: str | None = None

    try:
        doc = Document(str(file_path))
    except Exception:
        return []

    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        style_name = getattr(para.style, "name", "")
        if _is_heading(style_name, text):
            if outline_nodes and chapter_index < len(outline_nodes):
                current_chapter_temp_id = outline_nodes[chapter_index].temp_id
                chapter_index += 1
            continue

        idx = len(materials) + 1
        materials.append(
            {
                "temp_id": f"m{idx}",
                "chapter_temp_id": current_chapter_temp_id,
                "material_type": "fixed_paragraph",
                "title": text[:40],
                "content": text,
                "extract_as_candidate": False,
                "ignored": False,
                "variables": detect_variables(text),
            }
        )
    return materials
