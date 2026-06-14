from __future__ import annotations

from dataclasses import dataclass, field
import re

from src.services.docx_content_collector import RawBlock
from src.services.heading_level_detector import is_body_paragraph_style

_CHAPTER_ONE_RE = re.compile(r"^第一章\s*\S")
_MAIN_RESUME_NUMERIC_RE = re.compile(r"^\d+(?:\.\d+)+\S")


@dataclass
class MainOutlineSnapshot:
    last_seen_by_level: dict[int, int]
    section_anchor_level: int
    section_anchor_block: int | None
    structural_anchor_level: int
    structural_anchor_block: int | None
    max_open_level: int
    last_heading_level: int
    last_heading_pattern: str | None
    trigger_block_index: int
    trigger_title: str


@dataclass
class EmbeddedRegion:
    start_block_index: int
    end_block_index: int | None
    trigger_title: str
    resume_title: str | None = None
    skipped_heading_count: int = 0


@dataclass
class EmbeddedDocumentState:
    active: bool = False
    main_snapshot: MainOutlineSnapshot | None = None
    regions: list[EmbeddedRegion] = field(default_factory=list)
    skipped_heading_count: int = 0
    _current_region: EmbeddedRegion | None = None


def is_embedded_document_start(
    block: RawBlock,
    detection,
    *,
    max_open_level: int,
) -> bool:
    """Detect embedded attachment docs that restart with Normal-style 第一章."""
    if detection.pattern != "chinese_chapter":
        return False
    if not _CHAPTER_ONE_RE.match((block.text or "").strip()):
        return False
    if not is_body_paragraph_style(block.style_name):
        return False
    # Deep main outline already established; 第一章 on Normal is almost always an attachment.
    return max_open_level >= 2


def is_main_outline_resume(
    block: RawBlock,
    detection,
    *,
    embedded_active: bool,
) -> bool:
    if not embedded_active:
        return False
    if detection.pattern != "heading_style":
        return False
    if is_body_paragraph_style(block.style_name):
        return False
    return bool(_MAIN_RESUME_NUMERIC_RE.match((block.text or "").strip()))


def is_chinese_list_interim_resume(
    block: RawBlock,
    detection,
    *,
    embedded_active: bool,
) -> bool:
    """Exit an attachment island when the main outline resumes with 一、/二、/三、."""
    if not embedded_active:
        return False
    if detection.pattern != "chinese_list":
        return False
    return is_body_paragraph_style(block.style_name)


def is_vendor_subsection_resume(
    block: RawBlock,
    detection,
    *,
    embedded_active: bool,
) -> bool:
    return is_chinese_list_interim_resume(block, detection, embedded_active=embedded_active)


def begin_embedded_region(
    state: EmbeddedDocumentState,
    *,
    block: RawBlock,
    last_seen_by_level: dict[int, int],
    section_anchor_level: int,
    section_anchor_block: int | None,
    structural_anchor_level: int,
    structural_anchor_block: int | None,
    max_open_level: int,
    last_heading_level: int,
    last_heading_pattern: str | None,
) -> None:
    state.active = True
    state.main_snapshot = MainOutlineSnapshot(
        last_seen_by_level=dict(last_seen_by_level),
        section_anchor_level=section_anchor_level,
        section_anchor_block=section_anchor_block,
        structural_anchor_level=structural_anchor_level,
        structural_anchor_block=structural_anchor_block,
        max_open_level=max_open_level,
        last_heading_level=last_heading_level,
        last_heading_pattern=last_heading_pattern,
        trigger_block_index=block.index,
        trigger_title=block.text,
    )
    state._current_region = EmbeddedRegion(
        start_block_index=block.index,
        end_block_index=None,
        trigger_title=block.text,
    )
    state.regions.append(state._current_region)


def end_embedded_region(state: EmbeddedDocumentState, *, resume_title: str, end_block_index: int) -> None:
    if state._current_region is not None:
        state._current_region.end_block_index = end_block_index
        state._current_region.resume_title = resume_title
        state._current_region.skipped_heading_count = state.skipped_heading_count
    state.active = False
    state.main_snapshot = None
    state._current_region = None
    state.skipped_heading_count = 0


def restore_main_snapshot(snapshot: MainOutlineSnapshot) -> dict[str, object]:
    return {
        "last_seen_by_level": dict(snapshot.last_seen_by_level),
        "section_anchor_level": snapshot.section_anchor_level,
        "section_anchor_block": snapshot.section_anchor_block,
        "structural_anchor_level": snapshot.structural_anchor_level,
        "structural_anchor_block": snapshot.structural_anchor_block,
        "max_open_level": snapshot.max_open_level,
        "last_heading_level": snapshot.last_heading_level,
        "last_heading_pattern": snapshot.last_heading_pattern,
    }
