from __future__ import annotations

from dataclasses import dataclass, field
import re

from src.services.docx_content_collector import RawBlock
from src.services.embedded_document_detector import (
    EmbeddedDocumentState,
    begin_embedded_region,
    end_embedded_region,
    is_embedded_document_start,
    is_main_outline_resume,
    is_vendor_subsection_resume,
    restore_main_snapshot,
)
from src.services.heading_level_detector import (
    detect_heading_level,
    is_body_paragraph_style,
    is_numbered_body_paragraph,
    is_structural_section_pattern,
)

_RESET_NUMERIC_L1_RE = re.compile(r"^\s*\d+[\.、]\s+\S")
_MULTI_LEVEL_NUMERIC_RE = re.compile(r"^\s*\d+(?:\.\d+){2,}")
_NESTED_CN_PATTERNS = frozenset(
    {
        "chinese_list",
        "chinese_paren_list",
        "chinese_section",
    }
)
_SECTION_ANCHOR_PATTERNS = frozenset(
    {
        "heading_style",
        "numeric",
        "chinese_chapter",
        "markdown",
    }
)
_STRUCTURAL_ANCHOR_PATTERNS = frozenset(
    {
        "heading_style",
        "numeric",
        "chinese_chapter",
        "markdown",
    }
)


def _is_numeric_micro_outline_context(
    block: RawBlock,
    detection,
    *,
    last_heading_pattern: str | None,
    last_heading_level: int,
    structural_anchor_level: int,
) -> bool:
    """Normal-style numbered outline directly under a Heading section (e.g. 8.7 -> 1./1.1/)."""
    if detection.pattern != "numeric" or not is_body_paragraph_style(block.style_name):
        return False
    if is_numbered_body_paragraph(block.text, block.style_name, detection):
        return False
    if last_heading_pattern == "heading_style" and last_heading_level >= 2:
        return True
    if last_heading_pattern == "numeric" and structural_anchor_level >= 2:
        return True
    return False


def _effective_level(
    detection,
    *,
    structural_anchor_level: int,
    section_anchor_level: int,
    last_heading_pattern: str | None,
) -> int:
    if detection.pattern == "chinese_paren_list" and section_anchor_level > detection.level:
        return section_anchor_level + 1
    if (
        detection.pattern in {"chinese_list", "chinese_section"}
        and structural_anchor_level > detection.level
    ):
        return structural_anchor_level + 1
    if (
        detection.pattern == "numeric"
        and structural_anchor_level > detection.level
        and last_heading_pattern in {"heading_style", "numeric"}
    ):
        return structural_anchor_level + detection.level
    return detection.level


def _resolve_parent_block_index(
    level: int,
    last_seen_by_level: dict[int, int],
    *,
    structural_anchor_block: int | None,
    section_anchor_block: int | None,
    detection,
    structural_anchor_level: int,
    section_anchor_level: int,
) -> int | None:
    if (
        detection.pattern == "chinese_paren_list"
        and section_anchor_block is not None
        and section_anchor_level > detection.level
    ):
        return section_anchor_block
    if (
        detection.pattern == "chinese_list"
        and structural_anchor_block is not None
        and structural_anchor_level > detection.level
    ):
        return structural_anchor_block
    if (
        detection.pattern == "numeric"
        and structural_anchor_block is not None
        and structural_anchor_level > detection.level
        and detection.level == 1
    ):
        return structural_anchor_block
    if level <= 1:
        return None
    for parent_level in range(level - 1, 0, -1):
        if parent_level in last_seen_by_level:
            return last_seen_by_level[parent_level]
    return None


@dataclass
class InferredHeading:
    block_index: int
    title: str
    level: int
    parent_block_index: int | None
    pattern: str
    confidence: str


@dataclass
class InferResult:
    headings: list[InferredHeading]
    used_flat_fallback: bool
    patterns_used: list[str]
    medium_confidence_count: int
    embedded_regions: list = field(default_factory=list)
    embedded_heading_count: int = 0


def _should_skip_body_enumeration(
    block: RawBlock,
    detection,
    *,
    last_heading_level: int,
    last_heading_pattern: str | None,
    max_open_level: int,
    structural_anchor_level: int,
) -> bool:
    if is_numbered_body_paragraph(block.text, block.style_name, detection):
        return True
    if detection.pattern != "numeric" or not is_body_paragraph_style(block.style_name):
        return False
    if _is_numeric_micro_outline_context(
        block,
        detection,
        last_heading_pattern=last_heading_pattern,
        last_heading_level=last_heading_level,
        structural_anchor_level=structural_anchor_level,
    ):
        return False
    if detection.level == 1 and max_open_level >= 2:
        return True
    if (
        detection.level == 1
        and max_open_level >= 1
        and last_heading_level >= 1
        and is_structural_section_pattern(last_heading_pattern)
        and _RESET_NUMERIC_L1_RE.match(block.text.strip())
        and not re.match(r"^\s*\d+\.\d", block.text.strip())
    ):
        return True
    return False


def _update_anchor_state(
    *,
    block: RawBlock,
    detection,
    level: int,
    structural_anchor_level: int,
    structural_anchor_block: int | None,
    section_anchor_level: int,
    section_anchor_block: int | None,
) -> tuple[int, int | None, int, int | None]:
    if detection.pattern in _STRUCTURAL_ANCHOR_PATTERNS and _should_update_section_anchor(
        block, detection, level
    ):
        return level, block.index, level, block.index
    if detection.pattern == "numeric" and structural_anchor_level > 0:
        return structural_anchor_level, structural_anchor_block, section_anchor_level, section_anchor_block
    if detection.pattern == "chinese_list":
        return structural_anchor_level, structural_anchor_block, level, block.index
    if detection.pattern in _SECTION_ANCHOR_PATTERNS and _should_update_section_anchor(
        block, detection, level
    ):
        return level, block.index, level, block.index
    return structural_anchor_level, structural_anchor_block, section_anchor_level, section_anchor_block


def _should_update_section_anchor(block: RawBlock, detection, level: int) -> bool:
    if detection.pattern not in _SECTION_ANCHOR_PATTERNS:
        return False
    if detection.pattern == "numeric" and is_body_paragraph_style(block.style_name):
        stripped = (block.text or "").strip()
        return bool(_MULTI_LEVEL_NUMERIC_RE.match(stripped))
    return True


def _should_skip_vendor_attachment_numeric(
    block: RawBlock,
    detection,
    *,
    section_anchor_level: int,
    last_heading_pattern: str | None,
    max_open_level: int,
) -> bool:
    if detection.pattern != "numeric" or not is_body_paragraph_style(block.style_name):
        return False
    if section_anchor_level < 3 and max_open_level < 4:
        return False
    if last_heading_pattern not in {"chinese_list", "chinese_paren_list"}:
        return False
    stripped = (block.text or "").strip()
    if _MULTI_LEVEL_NUMERIC_RE.match(stripped):
        return False
    return True


def infer_hierarchy(blocks: list[RawBlock]) -> InferResult:
    headings: list[InferredHeading] = []
    last_seen_by_level: dict[int, int] = {}
    patterns: set[str] = set()
    medium_count = 0
    last_heading_level = 0
    last_heading_pattern: str | None = None
    max_open_level = 0
    section_anchor_level = 0
    section_anchor_block: int | None = None
    structural_anchor_level = 0
    structural_anchor_block: int | None = None
    embedded = EmbeddedDocumentState()

    for block in blocks:
        if block.block_type != "paragraph":
            continue
        detection = detect_heading_level(block.text, block.style_name)
        if detection is None:
            continue

        if not embedded.active and is_embedded_document_start(
            block,
            detection,
            max_open_level=max_open_level,
        ):
            begin_embedded_region(
                embedded,
                block=block,
                last_seen_by_level=last_seen_by_level,
                section_anchor_level=section_anchor_level,
                section_anchor_block=section_anchor_block,
                structural_anchor_level=structural_anchor_level,
                structural_anchor_block=structural_anchor_block,
                max_open_level=max_open_level,
                last_heading_level=last_heading_level,
                last_heading_pattern=last_heading_pattern,
            )
            embedded.skipped_heading_count += 1
            continue

        if embedded.active and (
            is_main_outline_resume(block, detection, embedded_active=True)
            or is_vendor_subsection_resume(block, detection, embedded_active=True)
        ):
            snapshot = embedded.main_snapshot
            end_embedded_region(
                embedded,
                resume_title=block.text,
                end_block_index=block.index,
            )
            if snapshot is not None:
                restored = restore_main_snapshot(snapshot)
                last_seen_by_level = restored["last_seen_by_level"]
                section_anchor_level = restored["section_anchor_level"]
                section_anchor_block = restored["section_anchor_block"]
                structural_anchor_level = restored["structural_anchor_level"]
                structural_anchor_block = restored["structural_anchor_block"]
                max_open_level = restored["max_open_level"]
                last_heading_level = restored["last_heading_level"]
                last_heading_pattern = restored["last_heading_pattern"]
            # fall through to append resumed heading

        elif embedded.active:
            embedded.skipped_heading_count += 1
            if embedded._current_region is not None:
                embedded._current_region.skipped_heading_count = embedded.skipped_heading_count
            continue

        if _should_skip_body_enumeration(
            block,
            detection,
            last_heading_level=last_heading_level,
            last_heading_pattern=last_heading_pattern,
            max_open_level=max_open_level,
            structural_anchor_level=structural_anchor_level,
        ):
            continue

        if _should_skip_vendor_attachment_numeric(
            block,
            detection,
            section_anchor_level=section_anchor_level,
            last_heading_pattern=last_heading_pattern,
            max_open_level=max_open_level,
        ):
            continue

        level = _effective_level(
            detection,
            structural_anchor_level=structural_anchor_level,
            section_anchor_level=section_anchor_level,
            last_heading_pattern=last_heading_pattern,
        )
        parent_block_index = _resolve_parent_block_index(
            level,
            last_seen_by_level,
            structural_anchor_block=structural_anchor_block,
            section_anchor_block=section_anchor_block,
            detection=detection,
            structural_anchor_level=structural_anchor_level,
            section_anchor_level=section_anchor_level,
        )

        headings.append(
            InferredHeading(
                block_index=block.index,
                title=block.text,
                level=level,
                parent_block_index=parent_block_index,
                pattern=detection.pattern,
                confidence=detection.confidence,
            )
        )
        last_seen_by_level[level] = block.index
        last_heading_level = level
        last_heading_pattern = detection.pattern
        max_open_level = max(max_open_level, level)
        (
            structural_anchor_level,
            structural_anchor_block,
            section_anchor_level,
            section_anchor_block,
        ) = _update_anchor_state(
            block=block,
            detection=detection,
            level=level,
            structural_anchor_level=structural_anchor_level,
            structural_anchor_block=structural_anchor_block,
            section_anchor_level=section_anchor_level,
            section_anchor_block=section_anchor_block,
        )
        patterns.add(detection.pattern)
        if detection.confidence == "medium":
            medium_count += 1
        for stale in list(last_seen_by_level):
            if stale > level:
                last_seen_by_level.pop(stale, None)

    total_embedded = sum(r.skipped_heading_count for r in embedded.regions)
    return InferResult(
        headings=headings,
        used_flat_fallback=len(headings) == 0,
        patterns_used=sorted(patterns),
        medium_confidence_count=medium_count,
        embedded_regions=embedded.regions,
        embedded_heading_count=total_embedded,
    )
