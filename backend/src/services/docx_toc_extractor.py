from __future__ import annotations

from dataclasses import dataclass
import enum
import logging
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree

from src.services.docx_content_collector import collect_content
from src.services.docx_document_walker import DocumentWalkResult
from src.services.docx_hierarchy_inferrer import infer_hierarchy
from src.services.docx_tree_materializer import materialize_outline_nodes
from src.services.text_sanitize import sanitize_pg_text

logger = logging.getLogger(__name__)

_DOC_XML_PATH = "word/document.xml"
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _WORD_NS}
_TRAILING_PAGE_RE = re.compile(r"\s+\d+\s*$")


class ExtractStrategy(str, enum.Enum):
    toc = "toc"
    heading_heuristic = "heading_heuristic"
    content_heuristic = "content_heuristic"
    flat_fallback = "flat_fallback"


@dataclass
class TocEntry:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int


@dataclass
class TocExtractResult:
    entries: list[TocEntry]
    strategy: ExtractStrategy


def _extract_toc_entries_from_docx_xml(path: Path) -> list[TocEntry]:
    try:
        with ZipFile(path, "r") as archive:
            document_xml = archive.read(_DOC_XML_PATH)
    except Exception:
        return []

    try:
        root = etree.fromstring(document_xml)
    except Exception:
        return []

    has_toc_field = any(
        "TOC" in ("".join(instr.itertext()) if instr is not None else "").upper()
        for instr in root.xpath(".//w:instrText", namespaces=_NS)
    )
    if not has_toc_field:
        return []

    entries: list[TocEntry] = []
    last_seen_by_level: dict[int, str] = {}
    for paragraph in root.xpath(".//w:p", namespaces=_NS):
        style_val = paragraph.xpath(
            "string(./w:pPr/w:pStyle/@w:val)",
            namespaces=_NS,
        )
        if not style_val:
            continue
        match = re.match(r"^toc(\d+)$", style_val.strip().lower())
        if not match:
            continue

        level = max(int(match.group(1)), 1)
        raw_title = "".join(paragraph.xpath(".//w:t/text()", namespaces=_NS))
        title = sanitize_pg_text(_TRAILING_PAGE_RE.sub("", " ".join(raw_title.split())).strip())
        if not title:
            continue

        parent_temp_id = None
        if level > 1:
            for parent_level in range(level - 1, 0, -1):
                parent_temp_id = last_seen_by_level.get(parent_level)
                if parent_temp_id:
                    break

        temp_id = f"n{len(entries) + 1}"
        entries.append(
            TocEntry(
                temp_id=temp_id,
                parent_temp_id=parent_temp_id,
                title=title,
                level=level,
                sort_order=len(entries),
            )
        )
        last_seen_by_level[level] = temp_id
        for stale_level in list(last_seen_by_level.keys()):
            if stale_level > level:
                last_seen_by_level.pop(stale_level, None)
    return entries


def _resolve_fallback_strategy(inferred) -> ExtractStrategy:
    if inferred.used_flat_fallback:
        return ExtractStrategy.flat_fallback
    if inferred.medium_confidence_count > 0:
        high_patterns = {"heading_style", "numeric"}
        if inferred.patterns_used and not any(p in high_patterns for p in inferred.patterns_used):
            return ExtractStrategy.content_heuristic
        if any(p not in high_patterns for p in inferred.patterns_used):
            return ExtractStrategy.content_heuristic
    return ExtractStrategy.heading_heuristic


def _entries_from_snapshot(snapshot: DocumentWalkResult) -> TocExtractResult:
    if snapshot.infer_result is None or snapshot.collected is None:
        raise ValueError("infer_snapshot missing infer_result or collected")
    nodes = materialize_outline_nodes(snapshot.infer_result, snapshot.collected.blocks)
    entries = [
        TocEntry(
            temp_id=node.temp_id,
            parent_temp_id=node.parent_temp_id,
            title=node.title,
            level=node.level,
            sort_order=node.sort_order,
        )
        for node in nodes
    ]
    strategy = _resolve_fallback_strategy(snapshot.infer_result)
    return TocExtractResult(entries=entries, strategy=strategy)


def _to_fallback_entries(path: Path) -> TocExtractResult:
    collected = collect_content(path)
    inferred = infer_hierarchy(collected.blocks)
    nodes = materialize_outline_nodes(inferred, collected.blocks)
    entries = [
        TocEntry(
            temp_id=node.temp_id,
            parent_temp_id=node.parent_temp_id,
            title=node.title,
            level=node.level,
            sort_order=node.sort_order,
        )
        for node in nodes
    ]
    strategy = _resolve_fallback_strategy(inferred)
    return TocExtractResult(entries=entries, strategy=strategy)


def extract_toc_entries(
    path: str | Path,
    *,
    infer_snapshot: DocumentWalkResult | None = None,
) -> TocExtractResult:
    file_path = Path(path)
    toc_entries = _extract_toc_entries_from_docx_xml(file_path)
    if toc_entries:
        return TocExtractResult(entries=toc_entries, strategy=ExtractStrategy.toc)
    if infer_snapshot is not None:
        if infer_snapshot.infer_result is not None and infer_snapshot.collected is not None:
            return _entries_from_snapshot(infer_snapshot)
        logger.warning(
            "extract_toc_entries incomplete infer_snapshot for %s; using path fallback",
            file_path,
        )
    return _to_fallback_entries(file_path)
