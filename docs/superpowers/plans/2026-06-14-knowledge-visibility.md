# 知识可见性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复文档候选章节切片（含图片块引用）、提供 media 访问 API，并交付正式知识浏览页（KU / Wiki / 手册资产）与候选/发布页富文本渲染。

**Architecture:** 后端新增 `content_blocks` + `section_content_builder` 聚合 heading 下正文为 `blocks_v1` JSON；解析期 `docx_image_extractor` 写 storage 与 `document_media_assets`；前端 `RichContentViewer` 统一渲染候选与正式知识；`/knowledge` 三 Tab 消费已有 list/get API。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, python-docx, Alembic | React 18, Ant Design 5, Vite, Vitest | pytest, httpx

**Design doc:** `docs/superpowers/specs/2026-06-14-knowledge-visibility-design.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/src/services/content_blocks.py` | blocks_v1 序列化、解析、excerpt、plain 降级 |
| `backend/src/services/section_content_builder.py` | 按 heading 边界聚合 DocumentTreeNode → blocks JSON |
| `backend/src/services/docx_image_extractor.py` | docx inline 图提取至 storage |
| `backend/src/models/document_media_asset.py` | 图片资产 ORM |
| `backend/src/api/routes/media.py` | `GET /kbs/{kb_id}/media/{asset_id}` |
| `backend/src/services/candidate_generate_service.py` | content 改用 section builder |
| `backend/src/services/actual_bid_parse_runner.py` | 解析流程接入 image extractor + content_ref |
| `backend/src/api/routes/candidates.py` | list 增加 `content_excerpt` |
| `backend/src/main.py` | 注册 media router |
| `backend/src/models/__init__.py` | 导出 DocumentMediaAsset |
| `backend/src/db/init_db.py` | import document_media_asset |
| `backend/alembic/versions/20260614_1600_document_media_assets.py` | 新表迁移 |
| `backend/tests/unit/test_content_blocks.py` | content_blocks 单测 |
| `backend/tests/unit/test_section_content_builder.py` | 切片边界单测 |
| `backend/tests/unit/test_docx_image_extractor.py` | 抽图单测 |
| `backend/tests/contract/test_media_api.py` | media API 契约 |
| `backend/tests/contract/test_candidates_list.py` | 扩展 content_excerpt 断言 |
| `backend/tests/integration/test_knowledge_visibility_flow.py` | 解析→候选→发布 E2E |
| `scripts/backfill_candidate_section_content.py` | 历史 pending 候选回填 |
| `frontend/src/components/RichContentViewer.tsx` | blocks_v1 / plain 渲染 |
| `frontend/src/components/RichContentViewer.test.tsx` | 组件单测 |
| `frontend/src/services/knowledgeAssets.ts` | KU / Wiki / ManualAsset API client |
| `frontend/src/pages/KnowledgeCenter/index.tsx` | 正式知识三 Tab 页 |
| `frontend/src/pages/KnowledgeCenter/KnowledgeDetailDrawer.tsx` | 详情 Drawer |
| `frontend/src/pages/CandidateCenter/index.tsx` | 列表加 content_excerpt 列 |
| `frontend/src/pages/CandidateCenter/CandidateDetailDrawer.tsx` | RichContentViewer |
| `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx` | 左栏 RichContentViewer + 预览 Tab |
| `frontend/src/services/candidates.ts` | CandidateListItem 加 content_excerpt |
| `frontend/src/App.tsx` | 路由 `/knowledge` |
| `frontend/src/layout/AppShell.tsx` | 导航「正式知识」 |

---

## Phase P0 — 章节切片与 content_excerpt

### Task P0-1: content_blocks 工具模块

**Files:**
- Create: `backend/src/services/content_blocks.py`
- Create: `backend/tests/unit/test_content_blocks.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_content_blocks.py
import json

from src.services.content_blocks import (
    blocks_v1,
    content_excerpt,
    parse_content,
)


def test_blocks_v1_serializes_paragraph():
    payload = blocks_v1([{"type": "paragraph", "text": "hello"}])
    parsed = json.loads(payload)
    assert parsed["format"] == "blocks_v1"
    assert parsed["blocks"][0]["text"] == "hello"


def test_content_excerpt_from_blocks():
    payload = blocks_v1(
        [
            {"type": "paragraph", "text": "第一段正文"},
            {"type": "table", "text": "A | B"},
        ]
    )
    assert content_excerpt(payload, max_len=10) == "第一段正文"


def test_content_excerpt_empty_blocks():
    assert content_excerpt(blocks_v1([]), max_len=120) == "（仅标题）"


def test_parse_content_plain_fallback():
    doc = parse_content("legacy plain text")
    assert doc.format == "plain"
    assert doc.plain_text == "legacy plain text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_content_blocks.py -v`  
Expected: FAIL with `ModuleNotFoundError: content_blocks`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/content_blocks.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

MAX_BLOCK_TEXT_CHARS = 32_000
EMPTY_EXCERPT = "（仅标题）"


@dataclass(frozen=True)
class ParsedContent:
    format: str
    blocks: list[dict[str, Any]]
    plain_text: str | None = None


def blocks_v1(blocks: list[dict[str, Any]]) -> str:
    safe_blocks: list[dict[str, Any]] = []
    for block in blocks:
        item = dict(block)
        text = item.get("text")
        if isinstance(text, str) and len(text) > MAX_BLOCK_TEXT_CHARS:
            item["text"] = text[:MAX_BLOCK_TEXT_CHARS]
        safe_blocks.append(item)
    return json.dumps({"format": "blocks_v1", "blocks": safe_blocks}, ensure_ascii=False)


def parse_content(raw: str | None) -> ParsedContent:
    if not raw:
        return ParsedContent(format="plain", blocks=[], plain_text="")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ParsedContent(format="plain", blocks=[], plain_text=raw)
    if isinstance(payload, dict) and payload.get("format") == "blocks_v1":
        blocks = payload.get("blocks") or []
        if not isinstance(blocks, list):
            blocks = []
        return ParsedContent(format="blocks_v1", blocks=blocks)
    return ParsedContent(format="plain", blocks=[], plain_text=raw)


def content_excerpt(raw: str | None, *, max_len: int = 120) -> str:
    doc = parse_content(raw)
    if doc.format == "plain":
        text = (doc.plain_text or "").strip()
        return text[:max_len] if text else EMPTY_EXCERPT
    for block in doc.blocks:
        if block.get("type") in {"paragraph", "table"}:
            text = str(block.get("text") or "").strip()
            if text:
                return text[:max_len]
        if block.get("type") == "image" and block.get("asset_id"):
            return "[图片]"
    return EMPTY_EXCERPT
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_content_blocks.py -v`  
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/content_blocks.py backend/tests/unit/test_content_blocks.py
git commit -m "feat: add content_blocks helpers for blocks_v1 format"
```

---

### Task P0-2: section_content_builder

**Files:**
- Create: `backend/src/services/section_content_builder.py`
- Create: `backend/tests/unit/test_section_content_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_section_content_builder.py
from uuid import uuid4

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.section_content_builder import build_section_content


def _node(
    *,
    document_id,
    sort_order: int,
    node_type: DocumentTreeNodeType,
    title: str | None = None,
    level: int | None = None,
    content_preview: str | None = None,
    content_ref: str | None = None,
):
    return DocumentTreeNode(
        node_id=uuid4(),
        kb_id=uuid4(),
        document_id=document_id,
        parent_id=None,
        node_type=node_type,
        title=title,
        level=level,
        sort_order=sort_order,
        content_preview=content_preview,
        content_ref=content_ref,
        tree_version=1,
    )


def test_build_section_content_collects_until_sibling_heading(db_session):
    document_id = uuid4()
    h1 = _node(
        document_id=document_id,
        sort_order=0,
        node_type=DocumentTreeNodeType.heading,
        title="技术方案",
        level=1,
        content_preview="技术方案",
    )
    p1 = _node(
        document_id=document_id,
        sort_order=1,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落一",
    )
    h2 = _node(
        document_id=document_id,
        sort_order=2,
        node_type=DocumentTreeNodeType.heading,
        title="子方案",
        level=2,
        content_preview="子方案",
    )
    p2 = _node(
        document_id=document_id,
        sort_order=3,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落二",
    )
    p3 = _node(
        document_id=document_id,
        sort_order=4,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落三",
    )
    db_session.add_all([h1, p1, h2, p2, p3])
    db_session.commit()

    content = build_section_content(
        db_session,
        document_id=document_id,
        heading_node_id=h1.node_id,
    )
    from src.services.content_blocks import parse_content

    doc = parse_content(content)
    texts = [b.get("text") for b in doc.blocks if b.get("type") == "paragraph"]
    assert texts == ["段落一", "段落三"]


def test_build_section_content_nested_heading_candidate(db_session):
    document_id = uuid4()
    h2 = _node(
        document_id=document_id,
        sort_order=2,
        node_type=DocumentTreeNodeType.heading,
        title="子方案",
        level=2,
        content_preview="子方案",
    )
    p2 = _node(
        document_id=document_id,
        sort_order=3,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落二",
    )
    db_session.add_all([h2, p2])
    db_session.commit()

    content = build_section_content(
        db_session,
        document_id=document_id,
        heading_node_id=h2.node_id,
    )
    from src.services.content_blocks import parse_content

    doc = parse_content(content)
    assert len(doc.blocks) == 1
    assert doc.blocks[0]["text"] == "段落二"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_section_content_builder.py -v`  
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/section_content_builder.py
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.content_blocks import blocks_v1


def build_section_content(
    db: Session,
    *,
    document_id: UUID,
    heading_node_id: UUID,
) -> str:
    nodes = (
        db.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == document_id)
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    heading = next((n for n in nodes if n.node_id == heading_node_id), None)
    if heading is None or heading.node_type != DocumentTreeNodeType.heading:
        return blocks_v1([])

    start_idx = next(i for i, n in enumerate(nodes) if n.node_id == heading_node_id)
    heading_level = heading.level or 1
    body_blocks: list[dict] = []

    for node in nodes[start_idx + 1 :]:
        if node.node_type == DocumentTreeNodeType.heading:
            node_level = node.level or heading_level
            if node_level <= heading_level:
                break
            continue
        if node.node_type == DocumentTreeNodeType.paragraph:
            text = (node.content_preview or "").strip()
            if text:
                body_blocks.append({"type": "paragraph", "text": text})
            continue
        if node.node_type == DocumentTreeNodeType.table:
            text = (node.content_preview or "").strip()
            if text:
                body_blocks.append({"type": "table", "text": text})
            continue
        if node.node_type == DocumentTreeNodeType.image:
            asset_id = (node.content_ref or "").strip() or None
            body_blocks.append(
                {
                    "type": "image",
                    "asset_id": asset_id,
                    "fallback": None if asset_id else "[image]",
                }
            )

    return blocks_v1(body_blocks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_section_content_builder.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/section_content_builder.py backend/tests/unit/test_section_content_builder.py
git commit -m "feat: aggregate heading section content into blocks_v1"
```

---

### Task P0-3: 接入 candidate_generate_service

**Files:**
- Modify: `backend/src/services/candidate_generate_service.py`
- Create: `backend/tests/unit/test_candidate_generate_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_candidate_generate_service.py
from uuid import uuid4

from src.models.candidate_knowledge import CandidateKnowledgeStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.candidate_generate_service import generate_for_document
from src.services.content_blocks import parse_content


def test_generate_for_document_uses_section_content(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="bid.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path=f"{seeded_kb.kb_id}/bid.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="标书",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    heading = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        node_type=DocumentTreeNodeType.heading,
        title="技术方案",
        level=1,
        sort_order=0,
        content_preview="技术方案",
        chapter_taxonomy_id=None,
        tree_version=1,
    )
    paragraph = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=1,
        content_preview="章节正文",
        tree_version=1,
    )
    db_session.add_all([heading, paragraph])
    db_session.commit()

    created = generate_for_document(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        document_id=document.document_id,
    )
    assert len(created) == 1
    doc = parse_content(created[0].content)
    assert any(b.get("text") == "章节正文" for b in doc.blocks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_candidate_generate_service.py -v`  
Expected: FAIL — content lacks paragraph block

- [ ] **Step 3: Update generate_for_document**

在 `backend/src/services/candidate_generate_service.py` 顶部增加 import：

```python
from src.services.section_content_builder import build_section_content
```

将创建候选时的 `content=node.content_preview` 改为：

```python
content=build_section_content(
    db,
    document_id=document_id,
    heading_node_id=node.node_id,
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_candidate_generate_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/candidate_generate_service.py backend/tests/unit/test_candidate_generate_service.py
git commit -m "feat: build section content when generating document candidates"
```

---

### Task P0-4: candidates list 返回 content_excerpt

**Files:**
- Modify: `backend/src/api/routes/candidates.py`
- Modify: `backend/tests/contract/test_candidates_list.py`

- [ ] **Step 1: Extend contract test**

在 `test_list_candidates_document_channel`（或新建 test）增加：

```python
def test_list_candidates_includes_content_excerpt(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"source_channel": "document", "status": "pending"},
    )
    assert resp.status_code == 200
    item = resp.json()["data"]["items"][0]
    assert item["content_excerpt"] == "完整正文内容"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_candidates_list.py::test_list_candidates_includes_content_excerpt -v`  
Expected: FAIL — KeyError `content_excerpt`

- [ ] **Step 3: Add excerpt to list serializers**

在 `backend/src/api/routes/candidates.py` 顶部：

```python
from src.services.content_blocks import content_excerpt
```

document 通道 rows.append 字典中增加：

```python
"content_excerpt": content_excerpt(candidate.content),
```

template stub 通道同理，对 `stub.content_preview` 调用 `content_excerpt(stub.content_preview)`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_candidates_list.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/candidates.py backend/tests/contract/test_candidates_list.py
git commit -m "feat: expose content_excerpt on candidate list API"
```

---

## Phase P1 — 图片提取与 Media API

### Task P1-1: document_media_assets 模型与迁移

**Files:**
- Create: `backend/src/models/document_media_asset.py`
- Create: `backend/alembic/versions/20260614_1600_document_media_assets.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/db/init_db.py`
- Create: `backend/tests/integration/test_document_media_asset_model.py`

- [ ] **Step 1: Write integration test**

```python
# backend/tests/integration/test_document_media_asset_model.py
from uuid import uuid4

from src.models.document_media_asset import DocumentMediaAsset


def test_create_document_media_asset(db_session, seeded_kb):
    document_id = uuid4()
    row = DocumentMediaAsset(
        kb_id=seeded_kb.kb_id,
        document_id=document_id,
        storage_path=f"{seeded_kb.kb_id}/media/{document_id}/img.png",
        mime_type="image/png",
        source_block_index=3,
    )
    db_session.add(row)
    db_session.commit()
    assert row.asset_id is not None
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_document_media_asset_model.py -v`

- [ ] **Step 3: Implement model**

```python
# backend/src/models/document_media_asset.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class DocumentMediaAsset(Base):
    __tablename__ = "document_media_assets"
    __table_args__ = (
        Index("ix_document_media_assets_kb_doc", "kb_id", "document_id"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_block_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Alembic migration 创建同名表（SQLite/Postgres 测试环境通过 `init_db` 亦可，但保留 migration 文件供生产）。

在 `backend/src/models/__init__.py` 与 `backend/src/db/init_db.py` 注册 `document_media_asset`。

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/document_media_asset.py backend/alembic/versions/20260614_1600_document_media_assets.py backend/src/models/__init__.py backend/src/db/init_db.py backend/tests/integration/test_document_media_asset_model.py
git commit -m "feat: add document_media_assets model and migration"
```

---

### Task P1-2: docx_image_extractor

**Files:**
- Create: `backend/src/services/docx_image_extractor.py`
- Create: `backend/tests/unit/test_docx_image_extractor.py`
- Create: `backend/tests/fixtures/sample-with-image.docx`（测试前用脚本生成，见 Step 3）

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_docx_image_extractor.py
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from docx import Document
from docx.shared import Inches
from PIL import Image

from src.services.docx_image_extractor import extract_docx_images


def _make_docx_with_image(path: Path) -> None:
    img = Image.new("RGB", (8, 8), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    doc = Document()
    doc.add_paragraph("before")
    doc.add_paragraph().add_run().add_picture(buf, width=Inches(1.0))
    doc.save(path)


def test_extract_docx_images_writes_storage_and_records(tmp_path):
    docx_path = tmp_path / "with-image.docx"
    _make_docx_with_image(docx_path)
    kb_id = uuid4()
    document_id = uuid4()
    storage_root = tmp_path / "storage"

    results = extract_docx_images(
        docx_path,
        storage_root=storage_root,
        kb_id=kb_id,
        document_id=document_id,
    )
    assert len(results) >= 1
    assert results[0].asset_id is not None
    assert (storage_root / results[0].storage_path).is_file()
    assert results[0].mime_type.startswith("image/")
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_docx_image_extractor.py -v`

- [ ] **Step 3: Implement extractor**

```python
# backend/src/services/docx_image_extractor.py
from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from docx import Document

from src.services.docx_block_reader import iter_document_blocks, paragraph_has_image, open_docx


@dataclass(frozen=True)
class ExtractedImage:
    asset_id: UUID
    storage_path: str
    mime_type: str
    source_block_index: int


def extract_docx_images(
    docx_path: str | Path,
    *,
    storage_root: Path,
    kb_id: UUID,
    document_id: UUID,
) -> list[ExtractedImage]:
    file_path = Path(docx_path)
    doc = open_docx(file_path)
    extracted: list[ExtractedImage] = []
    block_index = 0

    for block_type, block in iter_document_blocks(doc):
        if block_type != "paragraph":
            block_index += 1
            continue
        paragraph = block
        if not paragraph_has_image(paragraph):
            block_index += 1
            continue
        for run in paragraph.runs:
            if "graphic" not in run._element.xml and "drawing" not in run._element.xml:
                continue
            blips = run._element.xpath(".//a:blip")
            for blip in blips:
                embed = blip.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                )
                if not embed:
                    continue
                try:
                    part = doc.part.related_parts[embed]
                except KeyError:
                    continue
                blob = part.blob
                ext = mimetypes.guess_extension(part.content_type) or ".bin"
                asset_id = uuid4()
                rel_path = Path(str(kb_id)) / "media" / str(document_id) / f"{asset_id}{ext}"
                abs_path = storage_root / rel_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(blob)
                extracted.append(
                    ExtractedImage(
                        asset_id=asset_id,
                        storage_path=str(rel_path).replace("\\", "/"),
                        mime_type=part.content_type or "application/octet-stream",
                        source_block_index=block_index,
                    )
                )
        block_index += 1

    return extracted
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_image_extractor.py backend/tests/unit/test_docx_image_extractor.py
git commit -m "feat: extract inline docx images to storage"
```

---

### Task P1-3: 解析流程接入图片 + content_ref

**Files:**
- Modify: `backend/src/services/actual_bid_parse_runner.py`
- Modify: `backend/src/services/docx_tree_materializer.py`（纯图段落写入 block_index 映射供 runner 回填）

- [ ] **Step 1: Write integration test skeleton**

```python
# backend/tests/integration/test_knowledge_visibility_flow.py
def test_actual_bid_parse_candidate_content_has_blocks(client, db_session, seeded_kb, tmp_path):
    # 使用 tmp_path 放置带图 docx + 触发 parse + 断言 candidate.content 含 paragraph/image block
    ...
```

（实现时复用 `test_actual_bid_parse_trigger` 的 seed 模式；docx fixture 用 Task P1-2 的 `_make_docx_with_image`。）

- [ ] **Step 2: Wire extractor in `_persist_document_tree`**

在 `actual_bid_parse_runner.py` 中，document 创建后、`walk_document` 之前或之后：

1. 调用 `extract_docx_images(...)` 得到 `ExtractedImage` 列表。
2. 对每个结果 INSERT `DocumentMediaAsset`（需 db session）。
3. 构建 `block_index -> asset_id` 映射。
4. 持久化 tree node 时：若 `node_type=image`，设 `content_ref=str(asset_id)`；若 paragraph 含图且已有映射，在 materializer 层或 runner 层拆 block（MVP：纯 `[image]` 段落用映射，混合段落在 extractor 中记录 block_index）。

`docx_tree_materializer.py` 中纯图段落保留 `node_type=image`；runner 写 DB 时根据 `sort_order`/block index 查映射填 `content_ref`。

- [ ] **Step 3: Run integration test**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_visibility_flow.py -v`

- [ ] **Step 4: Commit**

```bash
git add backend/src/services/actual_bid_parse_runner.py backend/src/services/docx_tree_materializer.py backend/tests/integration/test_knowledge_visibility_flow.py
git commit -m "feat: persist docx images and link tree nodes to media assets"
```

---

### Task P1-4: Media API

**Files:**
- Create: `backend/src/api/routes/media.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/contract/test_media_api.py`

- [ ] **Step 1: Write contract test**

```python
# backend/tests/contract/test_media_api.py
from uuid import uuid4

from src.models.document_media_asset import DocumentMediaAsset


def test_get_media_asset_returns_image(client, db_session, seeded_kb, tmp_path, settings):
    document_id = uuid4()
    rel = f"{seeded_kb.kb_id}/media/{document_id}/test.png"
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    row = DocumentMediaAsset(
        kb_id=seeded_kb.kb_id,
        document_id=document_id,
        storage_path=rel,
        mime_type="image/png",
    )
    db_session.add(row)
    db_session.commit()

    resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/media/{row.asset_id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


def test_get_media_asset_wrong_kb_returns_404(client, db_session, seeded_kb):
    other_kb = uuid4()
    row = DocumentMediaAsset(
        kb_id=other_kb,
        document_id=uuid4(),
        storage_path="x/y/z.png",
        mime_type="image/png",
    )
    db_session.add(row)
    db_session.commit()
    resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/media/{row.asset_id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Implement route**

```python
# backend/src/api/routes/media.py
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.config import Settings
from src.db.session import get_db
from src.models.document_media_asset import DocumentMediaAsset
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/v1/kbs/{kb_id}/media", tags=["media"])


@router.get("/{asset_id}")
def get_media_asset(
    kb_id: UUID,
    asset_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(DocumentMediaAsset)
        .filter(DocumentMediaAsset.kb_id == kb_id)
        .filter(DocumentMediaAsset.asset_id == asset_id)
        .one_or_none()
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="media asset not found")
    abs_path = Path(Settings().storage_root) / row.storage_path
    if not abs_path.is_file():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="media file missing")
    return FileResponse(abs_path, media_type=row.mime_type)
```

`backend/src/main.py`：`from src.api.routes.media import router as media_router` 并 `app.include_router(media_router)`。

- [ ] **Step 3: Run tests — expect PASS**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_media_api.py -v`

- [ ] **Step 4: Commit**

```bash
git add backend/src/api/routes/media.py backend/src/main.py backend/tests/contract/test_media_api.py
git commit -m "feat: add read-only media asset API"
```

---

## Phase P1-5 — RichContentViewer 与候选 UI

### Task P1-5a: RichContentViewer 组件

**Files:**
- Create: `frontend/src/components/RichContentViewer.tsx`
- Create: `frontend/src/components/RichContentViewer.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/components/RichContentViewer.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RichContentViewer from "./RichContentViewer";

describe("RichContentViewer", () => {
  it("renders plain text fallback", () => {
    render(<RichContentViewer kbId="kb-1" content="hello world" />);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("renders blocks_v1 paragraph", () => {
    const content = JSON.stringify({
      format: "blocks_v1",
      blocks: [{ type: "paragraph", text: "段落内容" }],
    });
    render(<RichContentViewer kbId="kb-1" content={content} />);
    expect(screen.getByText("段落内容")).toBeInTheDocument();
  });

  it("renders image block with media url", () => {
    const content = JSON.stringify({
      format: "blocks_v1",
      blocks: [{ type: "image", asset_id: "asset-1" }],
    });
    render(<RichContentViewer kbId="kb-1" content={content} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", expect.stringContaining("/api/v1/kbs/kb-1/media/asset-1"));
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && npm test -- RichContentViewer.test.tsx`

- [ ] **Step 3: Implement component**

```tsx
// frontend/src/components/RichContentViewer.tsx
import { Empty, Typography } from "antd";

interface ContentBlock {
  type: string;
  text?: string;
  asset_id?: string | null;
  fallback?: string;
  alt?: string;
}

interface Props {
  kbId: string;
  content?: string | null;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function parseBlocks(raw?: string | null): { format: string; blocks: ContentBlock[]; plain?: string } {
  if (!raw) return { format: "plain", blocks: [], plain: "" };
  try {
    const payload = JSON.parse(raw);
    if (payload?.format === "blocks_v1" && Array.isArray(payload.blocks)) {
      return { format: "blocks_v1", blocks: payload.blocks };
    }
  } catch {
    /* plain */
  }
  return { format: "plain", blocks: [], plain: raw };
}

export default function RichContentViewer({ kbId, content }: Props) {
  const doc = parseBlocks(content);
  if (doc.format === "plain") {
    const text = (doc.plain ?? "").trim();
    return text ? (
      <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{text}</Typography.Paragraph>
    ) : (
      <Empty description="暂无正文" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    );
  }
  if (doc.blocks.length === 0) {
    return <Empty description="暂无正文" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {doc.blocks.map((block, idx) => {
        if (block.type === "paragraph" || block.type === "table") {
          return (
            <Typography.Paragraph key={idx} style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
              {block.text}
            </Typography.Paragraph>
          );
        }
        if (block.type === "image") {
          if (!block.asset_id) {
            return (
              <Typography.Text key={idx} type="secondary">
                {block.fallback ?? "[image]"}
              </Typography.Text>
            );
          }
          const src = `${API_BASE}/api/v1/kbs/${kbId}/media/${block.asset_id}`;
          return (
            <img
              key={idx}
              src={src}
              alt={block.alt ?? "image"}
              style={{ maxWidth: "100%", height: "auto" }}
            />
          );
        }
        return null;
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/RichContentViewer.tsx frontend/src/components/RichContentViewer.test.tsx
git commit -m "feat: add RichContentViewer for blocks_v1 content"
```

---

### Task P1-5b: 候选中心接入 RichContentViewer + content_excerpt 列

**Files:**
- Modify: `frontend/src/services/candidates.ts`
- Modify: `frontend/src/pages/CandidateCenter/index.tsx`
- Modify: `frontend/src/pages/CandidateCenter/CandidateDetailDrawer.tsx`
- Modify: `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx`

- [ ] **Step 1: Extend `CandidateListItem`**

```typescript
// frontend/src/services/candidates.ts — add to interface
content_excerpt?: string;
```

- [ ] **Step 2: Add table column in index.tsx**

```tsx
{
  title: "内容摘要",
  dataIndex: "content_excerpt",
  key: "content_excerpt",
  ellipsis: true,
  render: (value: string) => value || "（仅标题）",
},
```

- [ ] **Step 3: Replace plain text preview in drawers**

`CandidateDetailDrawer.tsx` 非 editable 分支：用 `<RichContentViewer kbId={kbId} content={detail.content} />` 替换 `Typography.Paragraph`。

`CandidateConfirmPage.tsx` 左栏正文区：同样改用 `RichContentViewer`。

- [ ] **Step 4: Manual smoke**

启动前后端，打开 `/candidates`，确认列表有摘要列、详情可见段落。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/candidates.ts frontend/src/pages/CandidateCenter/index.tsx frontend/src/pages/CandidateCenter/CandidateDetailDrawer.tsx frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx
git commit -m "feat: show content excerpt and rich preview in candidate center"
```

---

## Phase P2 — 正式知识浏览页

### Task P2-1: knowledgeAssets API client

**Files:**
- Create: `frontend/src/services/knowledgeAssets.ts`

- [ ] **Step 1: Implement clients**

```typescript
// frontend/src/services/knowledgeAssets.ts
import { apiRequest } from "./apiClient";

export interface KnowledgeUnitItem {
  ku_id: string;
  title: string;
  summary?: string | null;
  content: string;
  knowledge_type: string;
  status: string;
  candidate_id: string;
  import_id: string;
  source_doc_id?: string | null;
  searchable: boolean;
}

export interface WikiItem {
  wiki_id: string;
  title: string;
  summary?: string | null;
  content: string;
  wiki_type?: string | null;
  status: string;
  candidate_id: string;
  import_id: string;
  source_doc_id?: string | null;
}

export interface ManualAssetItem {
  manual_asset_id: string;
  title: string;
  summary?: string | null;
  content?: string | null;
  asset_type: string;
  storage_path?: string | null;
  status: string;
  candidate_id: string;
  import_id: string;
}

interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export async function listKnowledgeUnits(kbId: string, page = 1, pageSize = 20) {
  return apiRequest<Paged<KnowledgeUnitItem>>(
    `/api/v1/kbs/${kbId}/knowledge-units?page=${page}&page_size=${pageSize}`,
  );
}

export async function getKnowledgeUnit(kbId: string, kuId: string) {
  return apiRequest<KnowledgeUnitItem>(`/api/v1/kbs/${kbId}/knowledge-units/${kuId}`);
}

export async function listWikis(kbId: string, page = 1, pageSize = 20) {
  return apiRequest<Paged<WikiItem>>(`/api/v1/kbs/${kbId}/wikis?page=${page}&page_size=${pageSize}`);
}

export async function getWiki(kbId: string, wikiId: string) {
  return apiRequest<WikiItem>(`/api/v1/kbs/${kbId}/wikis/${wikiId}`);
}

export async function listManualAssets(kbId: string, page = 1, pageSize = 20) {
  return apiRequest<Paged<ManualAssetItem>>(
    `/api/v1/kbs/${kbId}/manual-assets?page=${page}&page_size=${pageSize}`,
  );
}

export async function getManualAsset(kbId: string, manualAssetId: string) {
  return apiRequest<ManualAssetItem>(`/api/v1/kbs/${kbId}/manual-assets/${manualAssetId}`);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/knowledgeAssets.ts
git commit -m "feat: add knowledge assets API client"
```

---

### Task P2-2: KnowledgeCenter 页面与路由

**Files:**
- Create: `frontend/src/pages/KnowledgeCenter/index.tsx`
- Create: `frontend/src/pages/KnowledgeCenter/KnowledgeDetailDrawer.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: Create KnowledgeDetailDrawer**

Drawer 接收 `assetType: "ku" | "wiki" | "manual_asset"`、`assetId`、`kbId`；按类型调 get API；正文用 `RichContentViewer`；Descriptions 展示来源链；手册资产若有 `storage_path` 显示下载链接（`/api/v1/...` 或 storage 只读 endpoint，MVP 可显示路径文本）。

- [ ] **Step 2: Create KnowledgeCenter/index.tsx**

Ant Design `Tabs` 三页签；每 Tab `Table` + 分页；列：标题、类型字段、摘要（client 侧从 content excerpt 或 summary）、状态、操作「查看」打开 Drawer。

关键词筛选 MVP：client 侧 filter `title`/`summary`（数据量小可接受）。

- [ ] **Step 3: Register route and nav**

`App.tsx`：

```tsx
import KnowledgeCenterPage from "./pages/KnowledgeCenter";
// ...
<Route path="/knowledge" element={<KnowledgeCenterPage />} />
```

`AppShell.tsx` NAV_ITEMS 在 candidates 后增加：

```tsx
{ key: "/knowledge", label: <Link to="/knowledge">正式知识</Link> },
```

- [ ] **Step 4: Manual smoke**

发布一条 KU 后访问 `/knowledge`，三 Tab 可列表、Drawer 可见正文与图片。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/KnowledgeCenter frontend/src/App.tsx frontend/src/layout/AppShell.tsx
git commit -m "feat: add formal knowledge center with KU Wiki manual asset tabs"
```

---

## Phase P3 — 回填脚本与编辑预览 Tab

### Task P3-1: backfill 脚本

**Files:**
- Create: `scripts/backfill_candidate_section_content.py`

- [ ] **Step 1: Implement script**

```python
#!/usr/bin/env python3
"""Backfill CandidateKnowledge.content using section_content_builder."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from uuid import UUID

from src.db.session import SessionLocal
from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus
from src.services.section_content_builder import build_section_content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb-id", required=True)
    parser.add_argument("--import-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kb_id = UUID(args.kb_id)
    updated = 0
    with SessionLocal() as db:
        q = db.query(CandidateKnowledge).filter(
            CandidateKnowledge.kb_id == kb_id,
            CandidateKnowledge.status == CandidateKnowledgeStatus.pending,
        )
        if args.import_id:
            q = q.filter(CandidateKnowledge.import_id == UUID(args.import_id))
        for row in q.all():
            if not row.source_doc_id or not row.source_node_id:
                continue
            new_content = build_section_content(
                db,
                document_id=row.source_doc_id,
                heading_node_id=row.source_node_id,
            )
            if new_content == row.content:
                continue
            updated += 1
            if not args.dry_run:
                row.content = new_content
        if not args.dry_run:
            db.commit()
    print(f"updated={updated} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Dry-run locally**

Run: `.venv/bin/python scripts/backfill_candidate_section_content.py --kb-id <UUID> --dry-run`

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_candidate_section_content.py
git commit -m "feat: add script to backfill candidate section content"
```

---

### Task P3-2: CandidateConfirmPage 编辑预览 Tab

**Files:**
- Modify: `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx`

- [ ] **Step 1: Add preview tab for pending candidates**

右栏「编辑」Tab 内：保留现有 Form TextArea；新增 Ant Design `Tabs` 子 Tab「编辑 | 预览」，预览 Tab 渲染：

```tsx
<RichContentViewer
  kbId={selectedKbId}
  content={editForm.getFieldValue("content") ?? candidate?.content}
/>
```

（plain 编辑内容在预览 Tab 仍走 plain 降级。）

- [ ] **Step 2: Update test if needed**

Run: `cd frontend && npm test -- CandidateConfirmPage.test.tsx`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx
git commit -m "feat: add content preview tab on candidate confirm page"
```

---

## Verification Checklist

- [ ] `cd backend && ../.venv/bin/pytest tests/unit/test_content_blocks.py tests/unit/test_section_content_builder.py tests/unit/test_docx_image_extractor.py -v`
- [ ] `cd backend && ../.venv/bin/pytest tests/contract/test_candidates_list.py tests/contract/test_media_api.py -v`
- [ ] `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_visibility_flow.py -v`
- [ ] `cd frontend && npm test -- RichContentViewer.test.tsx CandidateConfirmPage.test.tsx`
- [ ] 手动：解析含图 docx → 候选见正文+图 → 发布 KU → `/knowledge` 可见

---

## Plan Self-Review

| Spec 章节 | 对应 Task |
|-----------|-----------|
| §5 blocks_v1 | P0-1 |
| §6 章节切片 | P0-2, P0-3 |
| §7 图片管道 | P1-1, P1-2, P1-3, P1-4 |
| §8.2 正式知识页 | P2-1, P2-2 |
| §8.3 RichContentViewer | P1-5a |
| §8.4 候选中心 | P0-4, P1-5b, P3-2 |
| §9 content_excerpt API | P0-4 |
| §11 回填 | P3-1 |
| §12 测试 | 各 Task Steps |
| §13 P0–P3 切片 | Phase 对齐 |

**Placeholder scan:** 无 TBD；integration test Task P1-3 Step 1 需在实现时补全 fixture 触发逻辑（follow `test_actual_bid_parse_trigger.py`）。

**Type consistency:** `ExtractedImage.asset_id`、`content_ref`、`media API asset_id` 均为 UUID 字符串；前端 img src 一致。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-knowledge-visibility.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派生子 agent，Task 间人工 review，迭代快

**2. Inline Execution** — 本会话用 executing-plans 按 Phase 批量执行，检查点 review

Which approach?
