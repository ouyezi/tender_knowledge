from __future__ import annotations

from dataclasses import dataclass
import re

_HEADING_STYLE_RE = re.compile(r"^heading\s*(\d+)$", re.IGNORECASE)
_CN_HEADING_STYLE_RE = re.compile(r"^标题\s*(\d+)$")
_MARKDOWN_RE = re.compile(r"^(#{1,6})\s+\S")
_CHINESE_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百零〇两]+章\s*\S")
_CHINESE_SECTION_RE = re.compile(r"^第[一二三四五六七八九十百零〇两]+节\s*\S")
_CHINESE_LIST_RE = re.compile(r"^[一二三四五六七八九十百零〇两]+、\s*\S")
_CHINESE_PAREN_LIST_RE = re.compile(r"^（[一二三四五六七八九十百零〇两]+）\s*\S")
_NUMERIC_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[\.、]?\s+\S+")


@dataclass(frozen=True)
class HeadingDetection:
    level: int
    pattern: str
    confidence: str  # high | medium


def _level_from_heading_style(style_name: str | None) -> HeadingDetection | None:
    if not style_name:
        return None
    stripped = style_name.strip()
    lowered = stripped.lower()
    match = _HEADING_STYLE_RE.match(lowered.replace("  ", " "))
    if match:
        return HeadingDetection(level=max(int(match.group(1)), 1), pattern="heading_style", confidence="high")
    cn = _CN_HEADING_STYLE_RE.match(stripped)
    if cn:
        return HeadingDetection(level=max(int(cn.group(1)), 1), pattern="heading_style", confidence="high")
    if lowered.startswith("heading"):
        parts = lowered.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            return HeadingDetection(level=max(int(parts[-1]), 1), pattern="heading_style", confidence="high")
        return HeadingDetection(level=1, pattern="heading_style", confidence="high")
    return None


def detect_heading_level(text: str, style_name: str | None = None) -> HeadingDetection | None:
    stripped = (text or "").strip()
    if not stripped:
        return None

    style_hit = _level_from_heading_style(style_name)
    if style_hit is not None:
        return style_hit

    md = _MARKDOWN_RE.match(stripped)
    if md:
        return HeadingDetection(level=len(md.group(1)), pattern="markdown", confidence="medium")

    if _CHINESE_CHAPTER_RE.match(stripped):
        return HeadingDetection(level=1, pattern="chinese_chapter", confidence="medium")
    if _CHINESE_SECTION_RE.match(stripped):
        return HeadingDetection(level=2, pattern="chinese_section", confidence="medium")
    if _CHINESE_LIST_RE.match(stripped):
        return HeadingDetection(level=2, pattern="chinese_list", confidence="medium")
    if _CHINESE_PAREN_LIST_RE.match(stripped):
        return HeadingDetection(level=3, pattern="chinese_paren_list", confidence="medium")

    num = _NUMERIC_RE.match(stripped)
    if num:
        depth = num.group(1).rstrip(".").count(".") + 1
        return HeadingDetection(level=max(depth, 1), pattern="numeric", confidence="high")

    return None
