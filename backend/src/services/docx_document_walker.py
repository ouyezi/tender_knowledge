from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
import time
from collections.abc import Callable
from typing import Iterator

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[\.、]?\s+\S+")


def _sanitize_text(text: str) -> str:
    # PostgreSQL TEXT columns reject NUL bytes; docm/macros may leak binary fragments.
    return text.replace("\x00", "")


@dataclass
class WalkedNode:
    temp_id: str
    parent_temp_id: str | None
    section_temp_id: str | None
    node_type: str
    text: str
    level: int
    sort_order: int
    is_outline_node: bool = False
    needs_manual_review: bool = False


@dataclass
class DocumentWalkResult:
    nodes: list[WalkedNode]
    used_flat_fallback: bool = False
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


def _iter_document_blocks(doc: DocxDocument) -> Iterator[tuple[str, Paragraph | Table | object]]:
    body = doc.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, doc)
        else:
            yield "other", child


def _table_text(table: Table) -> str:
    lines: list[str] = []
    for row in table.rows:
        cells = [(cell.text or "").strip() for cell in row.cells]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _paragraph_has_image(paragraph: Paragraph) -> bool:
    return bool(paragraph._p.xpath(".//w:drawing"))


def walk_document(
    path: str | Path,
    *,
    on_block_progress: Callable[[int], None] | None = None,
    block_progress_interval: int = 200,
) -> DocumentWalkResult:
    file_path = Path(path)
    file_size = file_path.stat().st_size if file_path.exists() else 0
    logger.info(
        "walk_document START path=%s size_mb=%.1f",
        file_path,
        file_size / (1024 * 1024),
    )
    started = time.perf_counter()
    nodes: list[WalkedNode] = []
    heading_stack: list[tuple[int, str]] = []
    current_section_temp_id: str | None = None
    has_heading = False

    def append_node(
        *,
        node_type: str,
        text: str,
        level: int,
        parent_temp_id: str | None,
        section_temp_id: str | None,
        is_outline_node: bool,
    ) -> WalkedNode:
        idx = len(nodes) + 1
        node = WalkedNode(
            temp_id=f"n{idx}",
            parent_temp_id=parent_temp_id,
            section_temp_id=section_temp_id,
            node_type=node_type,
            text=_sanitize_text(text),
            level=level,
            sort_order=idx - 1,
            is_outline_node=is_outline_node,
        )
        nodes.append(node)
        return node

    try:
        logger.info("walk_document opening docx path=%s", file_path)
        open_started = time.perf_counter()
        doc = Document(str(file_path))
        logger.info(
            "walk_document docx opened path=%s elapsed_ms=%d",
            file_path,
            int((time.perf_counter() - open_started) * 1000),
        )
    except Exception:
        logger.exception("walk_document docx open failed, using text fallback path=%s", file_path)
        fallback_started = time.perf_counter()
        fallback_texts = _iter_paragraph_texts_from_fallback(file_path)
        logger.info(
            "walk_document text fallback lines=%d elapsed_ms=%d path=%s",
            len(fallback_texts),
            int((time.perf_counter() - fallback_started) * 1000),
            file_path,
        )
        fallback_nodes = [
            WalkedNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=None,
                section_temp_id=None,
                node_type="paragraph",
                text=text,
                level=1,
                sort_order=idx,
                is_outline_node=False,
                needs_manual_review=True,
            )
            for idx, text in enumerate(fallback_texts)
        ]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.warning(
            "walk_document DONE via text_fallback nodes=%d elapsed_ms=%d path=%s",
            len(fallback_nodes),
            elapsed_ms,
            file_path,
        )
        return DocumentWalkResult(
            nodes=fallback_nodes,
            used_flat_fallback=True,
            needs_manual_review=True,
        )

    block_count = 0
    logger.info("walk_document iterating blocks path=%s", file_path)
    for block_type, block in _iter_document_blocks(doc):
        block_count += 1
        if (
            on_block_progress is not None
            and block_progress_interval > 0
            and block_count % block_progress_interval == 0
        ):
            on_block_progress(block_count)

        if block_type == "paragraph":
            paragraph = block
            text = (paragraph.text or "").strip()
            has_image = _paragraph_has_image(paragraph)
            if not text and not has_image:
                continue

            is_heading, style_level = _is_heading_style(getattr(paragraph.style, "name", ""))
            numbered_level = _level_from_numbered_prefix(text) if not is_heading else None
            level = style_level if is_heading else numbered_level

            if level is not None:
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                parent_temp_id = heading_stack[-1][1] if heading_stack else None
                heading = append_node(
                    node_type="heading",
                    text=text,
                    level=level,
                    parent_temp_id=parent_temp_id,
                    section_temp_id=None,
                    is_outline_node=True,
                )
                heading.section_temp_id = heading.temp_id
                heading_stack.append((level, heading.temp_id))
                current_section_temp_id = heading.temp_id
                has_heading = True
                continue

            append_node(
                node_type="image" if has_image and not text else "paragraph",
                text=text or "[image]",
                level=0,
                parent_temp_id=current_section_temp_id,
                section_temp_id=current_section_temp_id,
                is_outline_node=False,
            )
            continue

        if block_type == "table":
            table = block
            table_text = _table_text(table).strip()
            if not table_text:
                continue
            append_node(
                node_type="table",
                text=table_text,
                level=0,
                parent_temp_id=current_section_temp_id,
                section_temp_id=current_section_temp_id,
                is_outline_node=False,
            )
            continue

        append_node(
            node_type="other",
            text=getattr(block, "tag", "unknown"),
            level=0,
            parent_temp_id=current_section_temp_id,
            section_temp_id=current_section_temp_id,
            is_outline_node=False,
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if not has_heading:
        for node in nodes:
            node.needs_manual_review = True
        logger.warning(
            "walk_document DONE no_heading flat_fallback nodes=%d blocks=%d elapsed_ms=%d path=%s",
            len(nodes),
            block_count,
            elapsed_ms,
            file_path,
        )
        return DocumentWalkResult(
            nodes=nodes,
            used_flat_fallback=True,
            needs_manual_review=True,
        )

    logger.info(
        "walk_document DONE nodes=%d blocks=%d elapsed_ms=%d path=%s",
        len(nodes),
        block_count,
        elapsed_ms,
        file_path,
    )
    return DocumentWalkResult(
        nodes=nodes,
        used_flat_fallback=False,
        needs_manual_review=False,
    )
