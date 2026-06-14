from __future__ import annotations

from dataclasses import dataclass

from src.services.docx_content_collector import RawBlock
from src.services.heading_level_detector import detect_heading_level


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


def infer_hierarchy(blocks: list[RawBlock]) -> InferResult:
    headings: list[InferredHeading] = []
    last_seen_by_level: dict[int, int] = {}
    patterns: set[str] = set()
    medium_count = 0

    for block in blocks:
        if block.block_type != "paragraph":
            continue
        detection = detect_heading_level(block.text, block.style_name)
        if detection is None:
            continue

        parent_block_index = None
        if detection.level > 1:
            for parent_level in range(detection.level - 1, 0, -1):
                if parent_level in last_seen_by_level:
                    parent_block_index = last_seen_by_level[parent_level]
                    break

        headings.append(
            InferredHeading(
                block_index=block.index,
                title=block.text,
                level=detection.level,
                parent_block_index=parent_block_index,
                pattern=detection.pattern,
                confidence=detection.confidence,
            )
        )
        last_seen_by_level[detection.level] = block.index
        patterns.add(detection.pattern)
        if detection.confidence == "medium":
            medium_count += 1
        for stale in list(last_seen_by_level):
            if stale > detection.level:
                last_seen_by_level.pop(stale, None)

    return InferResult(
        headings=headings,
        used_flat_fallback=len(headings) == 0,
        patterns_used=sorted(patterns),
        medium_confidence_count=medium_count,
    )
