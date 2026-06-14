# 标书目录层级推断（两阶段解析）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决 `flat_fallback` 扁平目录问题，通过两阶段解析（采集 → 推断 → 物化）为 Document Tree 与 Bid Outline 统一识别中文编号与 Markdown `#` 层级。

**Architecture:** 新增四个独立服务模块（`heading_level_detector`、`docx_content_collector`、`docx_hierarchy_inferrer`、`docx_tree_materializer`），由 `docx_document_walker` 与 `docx_outline_parser` 编排调用；`docx_toc_extractor` fallback 自动受益；新增 `content_heuristic` 抽取策略。

**Tech Stack:** Python 3.11, python-docx, pytest · 复用现有 `WalkedNode`/`OutlineNode`/`TocEntry` 数据结构

**Design doc:** `docs/superpowers/specs/2026-06-14-outline-hierarchy-inference-design.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/src/services/heading_level_detector.py` | 单块标题识别（中文编号/Markdown/样式/数字） |
| `backend/src/services/docx_block_reader.py` | 共享 docx 块遍历与表格/图片工具 |
| `backend/src/services/docx_content_collector.py` | Phase 1：扁平采集 RawBlock |
| `backend/src/services/docx_hierarchy_inferrer.py` | Phase 2：层级推断 InferredHeading |
| `backend/src/services/docx_tree_materializer.py` | Phase 3：物化 WalkedNode/OutlineNode |
| `backend/src/services/docx_document_walker.py` | 编排三阶段；保留 `walk_document()` 签名 |
| `backend/src/services/docx_outline_parser.py` | 复用推断管线生成 OutlineNode |
| `backend/src/services/docx_toc_extractor.py` | fallback 策略判定含 `content_heuristic` |
| `backend/src/models/bid_outline.py` | 枚举新增 `content_heuristic` |
| `backend/src/db/init_db.py` | PostgreSQL enum 同步 |
| `backend/src/services/actual_bid_parse_runner.py` | payload 写入 `hierarchy_inference` |
| `backend/tests/unit/test_heading_level_detector.py` | 检测器单测 |
| `backend/tests/unit/test_docx_hierarchy_inferrer.py` | 推断器单测 |
| `backend/tests/unit/test_docx_tree_materializer.py` | 物化器单测 |
| `backend/tests/unit/test_docx_document_walker.py` | walker 集成（中文编号） |
| `backend/tests/unit/test_docx_outline_parser.py` | outline 集成（中文编号） |
| `backend/tests/unit/test_docx_toc_extractor.py` | strategy=content_heuristic |
| `backend/tests/fixtures/sample-chinese-outline.docx` | 无 Heading/TOC 的中文编号夹具 |

**Run tests from:** `backend/` with `.venv/bin/pytest`

---

### Task 1: `heading_level_detector` 标题识别

**Files:**
- Create: `backend/src/services/heading_level_detector.py`
- Test: `backend/tests/unit/test_heading_level_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_heading_level_detector.py
import pytest

from src.services.heading_level_detector import detect_heading_level


@pytest.mark.parametrize(
    "text,style,expected_level,expected_pattern",
    [
        ("### 实施方案", None, 3, "markdown"),
        ("第一章 总则", None, 1, "chinese_chapter"),
        ("第一节 概述", None, 2, "chinese_section"),
        ("一、项目背景", None, 2, "chinese_list"),
        ("（一）建设目标", None, 3, "chinese_paren_list"),
        ("1.2.3 技术要求", None, 3, "numeric"),
        ("1 总则", None, 1, "numeric"),
        ("这是普通正文段落", None, None, None),
    ],
)
def test_detect_heading_level_patterns(text, style, expected_level, expected_pattern):
    result = detect_heading_level(text, style)
    if expected_level is None:
        assert result is None
        return
    assert result.level == expected_level
    assert result.pattern == expected_pattern


def test_detect_heading_style_takes_priority_over_markdown():
    result = detect_heading_level("### 标题", "Heading 2")
    assert result is not None
    assert result.pattern == "heading_style"
    assert result.level == 2
    assert result.confidence == "high"


def test_chinese_patterns_have_medium_confidence():
    result = detect_heading_level("第一章 总则", None)
    assert result is not None
    assert result.confidence == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/unit/test_heading_level_detector.py -v`  
Expected: FAIL `ModuleNotFoundError: heading_level_detector`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/heading_level_detector.py
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
    lowered = (style_name or "").strip().lower()
    if not lowered:
        return None
    match = _HEADING_STYLE_RE.match(lowered.replace("  ", " "))
    if not match:
        cn = _CN_HEADING_STYLE_RE.match(style_name.strip())
        if not cn:
            return None
        return HeadingDetection(level=max(int(cn.group(1)), 1), pattern="heading_style", confidence="high")
    return HeadingDetection(level=max(int(match.group(1)), 1), pattern="heading_style", confidence="high")


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/unit/test_heading_level_detector.py -v`  
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/heading_level_detector.py backend/tests/unit/test_heading_level_detector.py
git commit -m "feat: add heading level detector for Chinese and Markdown patterns"
```

---

### Task 2: 共享块读取 + Phase 1 `docx_content_collector`

**Files:**
- Create: `backend/src/services/docx_block_reader.py`
- Create: `backend/src/services/docx_content_collector.py`
- Test: `backend/tests/unit/test_docx_content_collector.py`（新建）

- [ ] **Step 1: Extract shared helpers from walker**

从 `docx_document_walker.py` 搬出（不改行为）到 `docx_block_reader.py`：

```python
# backend/src/services/docx_block_reader.py
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def sanitize_block_text(text: str) -> str:
    return text.replace("\x00", "")


def iter_document_blocks(doc: DocxDocument) -> Iterator[tuple[str, Paragraph | Table | object]]:
    body = doc.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, doc)
        else:
            yield "other", child


def table_text(table: Table) -> str:
    lines: list[str] = []
    for row in table.rows:
        cells = [(cell.text or "").strip() for cell in row.cells]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def paragraph_has_image(paragraph: Paragraph) -> bool:
    return bool(paragraph._p.xpath(".//w:drawing"))


def open_docx(path: Path) -> DocxDocument:
    return Document(str(path))
```

- [ ] **Step 2: Write failing collector test**

```python
# backend/tests/unit/test_docx_content_collector.py
from docx import Document

from src.services.docx_content_collector import collect_content


def _build_docx(path, lines):
    doc = Document()
    for style, text in lines:
        doc.add_paragraph(text, style=style)
    doc.save(path)


def test_collect_content_preserves_order_and_skips_empty(tmp_path):
    docx = tmp_path / "collect.docx"
    _build_docx(
        docx,
        [
            ("Normal", "第一章 总则"),
            ("Normal", ""),
            ("Normal", "正文段落"),
            ("Normal", "一、背景"),
        ],
    )
    result = collect_content(docx)
    texts = [b.text for b in result.blocks if b.block_type == "paragraph"]
    assert texts == ["第一章 总则", "正文段落", "一、背景"]
    assert [b.index for b in result.blocks] == [0, 1, 2]
```

- [ ] **Step 3: Implement collector**

```python
# backend/src/services/docx_content_collector.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.docx_block_reader import (
    iter_document_blocks,
    open_docx,
    paragraph_has_image,
    sanitize_block_text,
    table_text,
)


@dataclass
class RawBlock:
    index: int
    block_type: str
    text: str
    style_name: str | None
    has_image: bool


@dataclass
class CollectResult:
    blocks: list[RawBlock]


def collect_content(path: str | Path) -> CollectResult:
    file_path = Path(path)
    doc = open_docx(file_path)
    blocks: list[RawBlock] = []
    block_index = 0
    for block_type, block in iter_document_blocks(doc):
        if block_type == "paragraph":
            paragraph = block
            text = (paragraph.text or "").strip()
            has_image = paragraph_has_image(paragraph)
            if not text and not has_image:
                continue
            blocks.append(
                RawBlock(
                    index=block_index,
                    block_type="paragraph",
                    text=sanitize_block_text(text),
                    style_name=getattr(paragraph.style, "name", None),
                    has_image=has_image,
                )
            )
            block_index += 1
            continue
        if block_type == "table":
            text = table_text(block).strip()
            if not text:
                continue
            blocks.append(
                RawBlock(
                    index=block_index,
                    block_type="table",
                    text=sanitize_block_text(text),
                    style_name=None,
                    has_image=False,
                )
            )
            block_index += 1
            continue
        blocks.append(
            RawBlock(
                index=block_index,
                block_type="other",
                text=getattr(block, "tag", "unknown"),
                style_name=None,
                has_image=False,
            )
        )
        block_index += 1
    return CollectResult(blocks=blocks)
```

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_content_collector.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_block_reader.py backend/src/services/docx_content_collector.py backend/tests/unit/test_docx_content_collector.py
git commit -m "feat: add docx content collector phase for hierarchy inference"
```

---

### Task 3: Phase 2 `docx_hierarchy_inferrer`

**Files:**
- Create: `backend/src/services/docx_hierarchy_inferrer.py`
- Test: `backend/tests/unit/test_docx_hierarchy_inferrer.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_docx_hierarchy_inferrer.py
from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import infer_hierarchy


def _blocks(*lines: str) -> list[RawBlock]:
    return [
        RawBlock(index=i, block_type="paragraph", text=t, style_name="Normal", has_image=False)
        for i, t in enumerate(lines)
    ]


def test_infer_hierarchy_builds_parent_stack():
    blocks = _blocks("第一章 总则", "正文", "一、背景", "（一）目标", "1.1 细节")
    result = infer_hierarchy(blocks)
    assert result.used_flat_fallback is False
    levels = [h.level for h in result.headings]
    assert levels == [1, 2, 3, 2]
    assert result.headings[1].parent_block_index == 0
    assert result.headings[2].parent_block_index == 1


def test_infer_hierarchy_empty_headings_triggers_flat_fallback():
    blocks = _blocks("普通正文一段", "普通正文二段")
    result = infer_hierarchy(blocks)
    assert result.used_flat_fallback is True
    assert result.headings == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_hierarchy_inferrer.py -v`  
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement inferrer**

```python
# backend/src/services/docx_hierarchy_inferrer.py
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
```

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_hierarchy_inferrer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_hierarchy_inferrer.py backend/tests/unit/test_docx_hierarchy_inferrer.py
git commit -m "feat: add hierarchy inferrer with parent stack"
```

---

### Task 4: Phase 3 `docx_tree_materializer`

**Files:**
- Create: `backend/src/services/docx_tree_materializer.py`
- Test: `backend/tests/unit/test_docx_tree_materializer.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_docx_tree_materializer.py
from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import InferredHeading, InferResult
from src.services.docx_tree_materializer import materialize_walk_result


def test_materialize_assigns_content_to_section():
    blocks = [
        RawBlock(0, "paragraph", "第一章 总则", "Normal", False),
        RawBlock(1, "paragraph", "正文内容", "Normal", False),
        RawBlock(2, "table", "列A | 列B", None, False),
    ]
    inferred = InferResult(
        headings=[
            InferredHeading(0, "第一章 总则", 1, None, "chinese_chapter", "medium"),
        ],
        used_flat_fallback=False,
        patterns_used=["chinese_chapter"],
        medium_confidence_count=1,
    )
    result = materialize_walk_result(blocks, inferred)
    headings = [n for n in result.nodes if n.node_type == "heading"]
    paragraphs = [n for n in result.nodes if n.node_type == "paragraph"]
    tables = [n for n in result.nodes if n.node_type == "table"]
    assert len(headings) == 1
    assert headings[0].level == 1
    assert paragraphs[0].parent_temp_id == headings[0].temp_id
    assert tables[0].section_temp_id == headings[0].temp_id
    assert result.needs_manual_review is True
    assert result.used_flat_fallback is False


def test_materialize_flat_fallback_marks_all_review():
    blocks = [RawBlock(0, "paragraph", "只有正文", "Normal", False)]
    inferred = InferResult(headings=[], used_flat_fallback=True, patterns_used=[], medium_confidence_count=0)
    result = materialize_walk_result(blocks, inferred)
    assert result.used_flat_fallback is True
    assert all(n.needs_manual_review for n in result.nodes)
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_tree_materializer.py -v`

- [ ] **Step 3: Implement materializer**

```python
# backend/src/services/docx_tree_materializer.py
from __future__ import annotations

from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import InferResult
from src.services.docx_document_walker import DocumentWalkResult, WalkedNode


def _section_ranges(headings, block_count: int) -> list[tuple[int, int, int]]:
    """Return list of (heading_block_index, range_start, range_end)."""
    if not headings:
        return []
    indices = [h.block_index for h in headings]
    ranges: list[tuple[int, int, int]] = []
    for i, heading in enumerate(headings):
        start = heading.block_index + 1
        end = block_count
        for j in range(i + 1, len(headings)):
            if headings[j].level <= heading.level:
                end = headings[j].block_index
                break
        ranges.append((heading.block_index, start, end))
    return ranges


def materialize_walk_result(blocks: list[RawBlock], inferred: InferResult) -> DocumentWalkResult:
    nodes: list[WalkedNode] = []
    heading_temp_by_block: dict[int, str] = {}

    def append_node(**kwargs) -> WalkedNode:
        idx = len(nodes) + 1
        node = WalkedNode(temp_id=f"n{idx}", sort_order=idx - 1, **kwargs)
        nodes.append(node)
        return node

    if inferred.used_flat_fallback:
        for block in blocks:
            if block.block_type != "paragraph":
                continue
            append_node(
                parent_temp_id=None,
                section_temp_id=None,
                node_type="paragraph",
                text=block.text,
                level=1,
                is_outline_node=False,
                needs_manual_review=True,
            )
        # match legacy: promote all to flat L1 when no headings
        for node in nodes:
            node.node_type = "heading"
            node.is_outline_node = True
        return DocumentWalkResult(nodes=nodes, used_flat_fallback=True, needs_manual_review=True)

    heading_nodes: list[WalkedNode] = []
    for heading in inferred.headings:
        parent_temp_id = (
            heading_temp_by_block.get(heading.parent_block_index) if heading.parent_block_index is not None else None
        )
        node = append_node(
            parent_temp_id=parent_temp_id,
            section_temp_id=None,
            node_type="heading",
            text=heading.title,
            level=heading.level,
            is_outline_node=True,
            needs_manual_review=heading.confidence == "medium",
        )
        node.section_temp_id = node.temp_id
        heading_temp_by_block[heading.block_index] = node.temp_id
        heading_nodes.append(node)

    block_count = max((b.index for b in blocks), default=-1) + 1
    heading_block_set = {h.block_index for h in inferred.headings}
    section_by_block = {h.block_index: heading_temp_by_block[h.block_index] for h in inferred.headings}

    for block in blocks:
        if block.index in heading_block_set:
            continue
        section_temp_id = None
        for heading in reversed(inferred.headings):
            if heading.block_index < block.index:
                section_temp_id = section_by_block[heading.block_index]
                break
        node_type = block.block_type
        text = block.text if block.block_type != "image" else (block.text or "[image]")
        if block.block_type == "paragraph" and block.has_image and not block.text:
            node_type = "image"
            text = "[image]"
        append_node(
            parent_temp_id=section_temp_id,
            section_temp_id=section_temp_id,
            node_type=node_type,
            text=text,
            level=0,
            is_outline_node=False,
            needs_manual_review=False,
        )

    needs_review = inferred.medium_confidence_count > 0
    return DocumentWalkResult(
        nodes=nodes,
        used_flat_fallback=False,
        needs_manual_review=needs_review,
    )


def materialize_outline_nodes(inferred: InferResult, blocks: list[RawBlock]):
    from src.services.docx_outline_parser import OutlineNode

    if inferred.used_flat_fallback:
        paragraph_blocks = [b for b in blocks if b.block_type == "paragraph"]
        return [
            OutlineNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=None,
                title=b.text,
                level=1,
                sort_order=idx,
                needs_manual_review=True,
            )
            for idx, b in enumerate(paragraph_blocks)
        ]

    parent_map: dict[int, str] = {}
    nodes: list[OutlineNode] = []
    for idx, heading in enumerate(inferred.headings):
        parent_temp_id = parent_map.get(heading.parent_block_index) if heading.parent_block_index is not None else None
        temp_id = f"n{idx + 1}"
        nodes.append(
            OutlineNode(
                temp_id=temp_id,
                parent_temp_id=parent_temp_id,
                title=heading.title,
                level=heading.level,
                sort_order=idx,
                needs_manual_review=heading.confidence == "medium",
            )
        )
        parent_map[heading.block_index] = temp_id
    return nodes
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_tree_materializer.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_tree_materializer.py backend/tests/unit/test_docx_tree_materializer.py
git commit -m "feat: add tree materializer for walked and outline nodes"
```

---

### Task 5: 重构 `docx_document_walker` 编排三阶段

**Files:**
- Modify: `backend/src/services/docx_document_walker.py`
- Modify: `backend/tests/unit/test_docx_document_walker.py`

- [ ] **Step 1: Add Chinese outline fixture builder in test**

```python
# append to backend/tests/unit/test_docx_document_walker.py
from docx import Document

def _build_chinese_outline_docx(path: Path) -> None:
    doc = Document()
    for text in [
        "第一章 项目概述",
        "本项目旨在建设数字化平台。",
        "一、建设背景",
        "背景说明正文。",
        "### 技术路线",
        "技术细节正文。",
    ]:
        doc.add_paragraph(text, style="Normal")
    doc.save(path)


def test_walk_document_detects_chinese_hierarchy(tmp_path):
    docx = tmp_path / "chinese.docx"
    _build_chinese_outline_docx(docx)
    result = walk_document(docx)
    assert result.used_flat_fallback is False
    headings = [n for n in result.nodes if n.node_type == "heading"]
    assert [h.level for h in headings] == [1, 2, 3]
    paragraphs = [n for n in result.nodes if n.node_type == "paragraph"]
    assert all(p.parent_temp_id is not None for p in paragraphs)
```

- [ ] **Step 2: Run test — expect FAIL** (`used_flat_fallback` still True)

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_document_walker.py::test_walk_document_detects_chinese_hierarchy -v`

- [ ] **Step 3: Refactor walker**

将 `walk_document` 主体替换为：

```python
from src.services.docx_block_reader import open_docx
from src.services.docx_content_collector import collect_content
from src.services.docx_hierarchy_inferrer import infer_hierarchy
from src.services.docx_tree_materializer import materialize_walk_result

# 保留 WalkedNode / DocumentWalkResult 定义与 text-fallback 分支
# docx 成功打开后：
collected = collect_content(file_path)
inferred = infer_hierarchy(collected.blocks)
result = materialize_walk_result(collected.blocks, inferred)
# 保留 on_block_progress：在 collect 循环中按 block 计数回调
# 保留现有 logging 字段（nodes/blocks/elapsed_ms）
return result
```

删除 walker 内重复的 `_is_heading_style`、`_level_from_numbered_prefix`、`_iter_document_blocks` 等（已迁至 `docx_block_reader` / detector）。

- [ ] **Step 4: Run all walker tests**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_document_walker.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_document_walker.py backend/tests/unit/test_docx_document_walker.py
git commit -m "refactor: walk_document uses three-phase hierarchy pipeline"
```

---

### Task 6: 重构 `docx_outline_parser` + `docx_toc_extractor` 策略

**Files:**
- Modify: `backend/src/services/docx_outline_parser.py`
- Modify: `backend/src/services/docx_toc_extractor.py`
- Modify: `backend/tests/unit/test_docx_outline_parser.py`
- Modify: `backend/tests/unit/test_docx_toc_extractor.py`

- [ ] **Step 1: Add failing outline test for Chinese numbering**

```python
# append to backend/tests/unit/test_docx_outline_parser.py
def test_parse_outline_detects_chinese_numbering(tmp_path):
    docx_path = tmp_path / "chinese.docx"
    _build_docx(
        docx_path,
        [
            ("Normal", "第一章 总则"),
            ("Normal", "一、适用范围"),
            ("Normal", "（一）适用对象"),
        ],
    )
    nodes = parse_outline(docx_path)
    assert [n.level for n in nodes] == [1, 2, 3]
    assert nodes[1].parent_temp_id == nodes[0].temp_id
    assert all(n.needs_manual_review for n in nodes)
```

- [ ] **Step 2: Refactor parse_outline**

```python
# backend/src/services/docx_outline_parser.py — parse_outline 新实现
from src.services.docx_content_collector import collect_content
from src.services.docx_hierarchy_inferrer import infer_hierarchy
from src.services.docx_tree_materializer import materialize_outline_nodes

def parse_outline(path: str | Path) -> list[OutlineNode]:
    file_path = Path(path)
    try:
        collected = collect_content(file_path)
    except Exception:
        # 保留原有文本 fallback
        ...
    inferred = infer_hierarchy(collected.blocks)
    return materialize_outline_nodes(inferred, collected.blocks)
```

- [ ] **Step 3: Extend ExtractStrategy and fallback logic**

```python
# backend/src/services/docx_toc_extractor.py
class ExtractStrategy(str, enum.Enum):
    toc = "toc"
    heading_heuristic = "heading_heuristic"
    content_heuristic = "content_heuristic"
    flat_fallback = "flat_fallback"


def _resolve_fallback_strategy(nodes: list) -> ExtractStrategy:
    if not nodes:
        return ExtractStrategy.flat_fallback
    if all(node.needs_manual_review for node in nodes):
        # 区分：flat_fallback（全 L1 段落）vs content_heuristic（有层级但需审核）
        if len(set(node.level for node in nodes)) == 1 and all(node.level == 1 for node in nodes):
            return ExtractStrategy.flat_fallback
        return ExtractStrategy.content_heuristic
    patterns = {getattr(n, "pattern", None) for n in nodes}  # 通过 infer 元数据或 needs_manual_review 判定
    if any(node.needs_manual_review for node in nodes):
        return ExtractStrategy.content_heuristic
    return ExtractStrategy.heading_heuristic
```

实现提示：`materialize_outline_nodes` 返回的 `OutlineNode` 无 `pattern` 字段；策略判定可改为在 `parse_outline` 返回 `(nodes, infer_meta)` 或在 `_to_fallback_entries` 内重新调用 `infer_hierarchy` 读取 `patterns_used` / `medium_confidence_count`。

推荐：`_to_fallback_entries` 内：

```python
collected = collect_content(path)
inferred = infer_hierarchy(collected.blocks)
nodes = materialize_outline_nodes(inferred, collected.blocks)
if inferred.used_flat_fallback:
    strategy = ExtractStrategy.flat_fallback
elif inferred.medium_confidence_count > 0 and not any(
    p in inferred.patterns_used for p in ("heading_style", "numeric")
):
    strategy = ExtractStrategy.content_heuristic
elif inferred.medium_confidence_count > 0:
    strategy = ExtractStrategy.content_heuristic
else:
    strategy = ExtractStrategy.heading_heuristic
```

- [ ] **Step 4: Add toc extractor test**

```python
# append to backend/tests/unit/test_docx_toc_extractor.py
def test_extract_toc_uses_content_heuristic_for_chinese_outline(tmp_path):
    from docx import Document
    doc = Document()
    for text in ["第一章 总则", "一、背景"]:
        doc.add_paragraph(text, style="Normal")
    path = tmp_path / "ch.docx"
    doc.save(path)
    result = extract_toc_entries(path)
    assert result.strategy == ExtractStrategy.content_heuristic
    assert result.entries[0].level == 1
    assert result.entries[1].parent_temp_id == result.entries[0].temp_id
```

- [ ] **Step 5: Run tests**

Run: `cd backend && .venv/bin/pytest tests/unit/test_docx_outline_parser.py tests/unit/test_docx_toc_extractor.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/docx_outline_parser.py backend/src/services/docx_toc_extractor.py backend/tests/unit/test_docx_outline_parser.py backend/tests/unit/test_docx_toc_extractor.py
git commit -m "feat: outline parser and toc extractor use content heuristic strategy"
```

---

### Task 7: 枚举 `content_heuristic` + runner 可观测性

**Files:**
- Modify: `backend/src/models/bid_outline.py`
- Modify: `backend/src/db/init_db.py`
- Modify: `backend/src/services/actual_bid_parse_runner.py`
- Modify: `backend/tests/integration/test_actual_bid_parse_runner.py`（如需要）

- [ ] **Step 1: Add enum value**

```python
# backend/src/models/bid_outline.py
class BidOutlineExtractStrategy(str, enum.Enum):
    toc = "toc"
    heading_heuristic = "heading_heuristic"
    content_heuristic = "content_heuristic"
    flat_fallback = "flat_fallback"
```

- [ ] **Step 2: Sync PostgreSQL enum in init_db**

```python
# backend/src/db/init_db.py — in init_db() with block:
from src.models.bid_outline import BidOutlineExtractStrategy

_sync_postgres_enum(
    conn,
    "bidoutlineextractstrategy",
    [member.value for member in BidOutlineExtractStrategy],
)
```

- [ ] **Step 3: Extend parse suggestion payload**

在 `actual_bid_parse_runner._persist_parse_suggestion` 的 `payload` 中，于 `walk_result` 旁增加：

```python
from src.services.docx_content_collector import collect_content
from src.services.docx_hierarchy_inferrer import infer_hierarchy

collected = collect_content(docx_path)
inferred = infer_hierarchy(collected.blocks)
suggestion.payload["hierarchy_inference"] = {
    "heading_count": len(inferred.headings),
    "patterns_used": inferred.patterns_used,
    "used_flat_fallback": inferred.used_flat_fallback,
    "medium_confidence_count": inferred.medium_confidence_count,
}
```

为避免重复解析，可将 `infer_hierarchy` 结果从 `walk_document` 返回（扩展 `DocumentWalkResult` 增加可选 `infer_meta` 字段）——优先选此方式避免双遍 IO。

- [ ] **Step 4: Run integration test**

Run: `cd backend && .venv/bin/pytest tests/integration/test_actual_bid_parse_runner.py -v`  
Expected: PASS（既有用例不因 enum 扩展失败）

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/bid_outline.py backend/src/db/init_db.py backend/src/services/actual_bid_parse_runner.py backend/src/services/docx_document_walker.py
git commit -m "feat: add content_heuristic strategy and hierarchy inference telemetry"
```

---

### Task 8: 夹具与全量回归

**Files:**
- Create: `backend/tests/fixtures/sample-chinese-outline.docx`（可用脚本或测试 helper 生成并提交）
- Modify: `backend/tests/unit/test_docx_document_walker.py`（改用 fixtures 路径）

- [ ] **Step 1: Generate and commit fixture**

```python
# scripts/generate_chinese_outline_fixture.py（一次性脚本，生成后提交 bin）
from pathlib import Path
from docx import Document

out = Path("backend/tests/fixtures/sample-chinese-outline.docx")
doc = Document()
for text in [
    "第一章 项目概述",
    "概述正文。",
    "一、建设目标",
    "目标正文。",
    "### 技术架构",
    "架构正文。",
]:
    doc.add_paragraph(text, style="Normal")
doc.save(out)
```

Run: `cd backend && .venv/bin/python ../scripts/generate_chinese_outline_fixture.py`

- [ ] **Step 2: Full regression**

Run: `cd backend && .venv/bin/pytest tests/unit/test_heading_level_detector.py tests/unit/test_docx_content_collector.py tests/unit/test_docx_hierarchy_inferrer.py tests/unit/test_docx_tree_materializer.py tests/unit/test_docx_document_walker.py tests/unit/test_docx_outline_parser.py tests/unit/test_docx_toc_extractor.py tests/integration/test_actual_bid_parse_runner.py -v`  
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/fixtures/sample-chinese-outline.docx scripts/generate_chinese_outline_fixture.py
git commit -m "test: add Chinese outline fixture and verify hierarchy inference"
```

---

## Spec Coverage Check

| Spec 要求 | Task |
|-----------|------|
| Phase 1 content_collect | Task 2 |
| Phase 2 hierarchy_infer + detector | Task 1, 3 |
| Phase 3 tree_materialize | Task 4 |
| walker 编排 | Task 5 |
| outline_parser 复用 | Task 6 |
| content_heuristic 策略 | Task 6, 7 |
| hierarchy_inference payload | Task 7 |
| 中文编号/Markdown 单测 | Task 1, 3, 5, 6 |
| flat_fallback 向后兼容 | Task 4, 5 |
| fixture | Task 8 |
| LLM/版式不做 | — (out of scope) |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-outline-hierarchy-inference.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间做 review，迭代快

**2. Inline Execution** — 在本会话用 executing-plans 按 Task 批量执行，checkpoint 处暂停确认

Which approach?
