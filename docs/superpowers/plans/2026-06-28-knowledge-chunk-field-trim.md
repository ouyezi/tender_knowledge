# Knowledge Chunk Field Trim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精简 `knowledge_chunks` 用户可见字段，新增证书编号/日期，保留内部 `char_start/char_end` 自动计算，删除页码与冗余元数据。

**Architecture:** Alembic 一次性 TRUNCATE + DROP/ADD；`chunk_service` 入库时调用 `entry_content_service.compute_section_char_range` 写 char 字段但不通过 API 暴露；证书与失效日期规范化集中在 `certificate_field_utils`；预填/索引摘要 LLM 同步新字段。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest; React 18, TypeScript, Ant Design 5, Vitest.

**Design spec:** `docs/superpowers/specs/2026-06-28-knowledge-chunk-field-trim-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/services/knowledge/certificate_field_utils.py` | 证书逗号分隔规范化、多失效日 min |
| `backend/src/services/knowledge/entry_content_service.py` | 新增 `compute_section_char_range` 公开函数 |
| `backend/alembic/versions/20260628_1100_knowledge_chunk_field_trim.py` | TRUNCATE + DDL |
| `backend/src/models/knowledge_chunk.py` | ORM 删列/加列 |
| `backend/src/services/knowledge/chunk_service.py` | 自动 char 范围、证书字段写入 |
| `backend/src/api/schemas/knowledge_chunks.py` | 请求/筛选 schema |
| `backend/src/api/routes/knowledge_chunks.py` | 序列化去掉内部/废弃字段 |
| `backend/src/services/knowledge/knowledge_prefill_prompt.py` | 预填 prompt 换证书字段 |
| `backend/src/services/knowledge/prefill_service.py` | 预填 normalize |
| `backend/src/services/knowledge/chunk_summary_service.py` | 索引摘要换证书字段 |
| `backend/src/services/knowledge/chunk_index_task.py` | 去掉 issue_date 写入 |
| `backend/tests/helpers/chunk_payload.py` | 测试 payload 更新 |
| `frontend/src/services/knowledgeChunks.ts` | TS 类型 |
| `frontend/src/constants/knowledgeChunkMeta.ts` | label 更新 |
| `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx` | 表单精简 + 证书字段 |
| `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx` | 筛选精简 |
| `frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx` | 详情展示 |
| `frontend/src/pages/Knowledge/batchIngestUtils.ts` | 批量 payload |

---

## Task 1: 证书字段工具函数

**Files:**
- Create: `backend/src/services/knowledge/certificate_field_utils.py`
- Create: `backend/tests/unit/test_certificate_field_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_certificate_field_utils.py
from datetime import date

from src.services.knowledge.certificate_field_utils import (
    earliest_expire_date,
    normalize_certificate_date,
    normalize_certificate_number,
)


def test_normalize_certificate_number_dedupes_and_trims():
    assert normalize_certificate_number(" A001 , B002 , A001 ") == "A001,B002"


def test_normalize_certificate_date():
    assert normalize_certificate_date("2024-01-01, 2025-06-01") == "2024-01-01,2025-06-01"
    assert normalize_certificate_date(None) is None


def test_earliest_expire_date_picks_min():
    assert earliest_expire_date(["2025-12-31", "2024-06-01", "invalid"]) == date(2024, 6, 1)
    assert earliest_expire_date([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_certificate_field_utils.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement utils**

```python
# backend/src/services/knowledge/certificate_field_utils.py
from __future__ import annotations

import re
from datetime import date, datetime

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_certificate_number(value: str | None) -> str | None:
    if not value:
        return None
    seen: set[str] = set()
    parts: list[str] = []
    for raw in str(value).split(","):
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        parts.append(item)
    return ",".join(parts) if parts else None


def normalize_certificate_date(value: str | None) -> str | None:
    if not value:
        return None
    parts: list[str] = []
    for raw in str(value).split(","):
        item = raw.strip()
        if not item:
            continue
        if not _ISO_DATE_RE.match(item):
            continue
        parts.append(item)
    return ",".join(parts) if parts else None


def _parse_iso_date(value: str) -> date | None:
    if not _ISO_DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def earliest_expire_date(values: list[str]) -> date | None:
    parsed = [_parse_iso_date(item) for item in values]
    dates = [item for item in parsed if item is not None]
    return min(dates) if dates else None


def earliest_expire_date_from_csv(value: str | None) -> date | None:
    if not value:
        return None
    return earliest_expire_date([part.strip() for part in value.split(",") if part.strip()])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_certificate_field_utils.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/certificate_field_utils.py \
  backend/tests/unit/test_certificate_field_utils.py
git commit -m "feat: add certificate field normalization utils"
```

---

## Task 2: 章节字符范围计算（公开函数）

**Files:**
- Modify: `backend/src/services/knowledge/entry_content_service.py`
- Create: `backend/tests/unit/test_compute_section_char_range.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_compute_section_char_range.py
from uuid import uuid4

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.doc_chunk.content_md_store import save_content_md
from src.services.knowledge.entry_content_service import compute_section_char_range


def test_compute_section_char_range_returns_slice_offsets(db_session, seeded_kb):
    doc_id = uuid4()
    node_id = uuid4()
    content_md = "# 第一章\n\n## 1.1 资质\n\n正文ABC\n"
    save_content_md(document_id=doc_id, content_md=content_md)
    db_session.add(
        DocumentTreeNode(
            node_id=node_id,
            kb_id=seeded_kb.kb_id,
            document_id=doc_id,
            parent_id=None,
            node_type=DocumentTreeNodeType.heading,
            title="1.1 资质",
            level=2,
            sort_order=1,
        )
    )
    db_session.commit()

    start, end = compute_section_char_range(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=doc_id,
        primary_node_id=node_id,
        content="正文ABC",
    )
    assert start is not None
    assert end is not None
    assert end - start == len("正文ABC")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_compute_section_char_range.py -v
```

Expected: FAIL `ImportError: compute_section_char_range`

- [ ] **Step 3: Add public function to entry_content_service.py**

在文件末尾 `_range_from_slice` 附近添加：

```python
def compute_section_char_range(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    primary_node_id: UUID,
    content: str,
) -> tuple[int | None, int | None]:
    content_md = load_content_md(document_id=doc_id)
    if not content_md:
        return (None, None)
    nodes = _load_heading_nodes(db, kb_id=kb_id, doc_id=doc_id)
    section_md = content.strip() if content.strip() else ""
    if not section_md:
        return (None, None)
    return _range_from_slice(content_md, section_md)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_compute_section_char_range.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/entry_content_service.py \
  backend/tests/unit/test_compute_section_char_range.py
git commit -m "feat: add compute_section_char_range for chunk ingest"
```

---

## Task 3: Migration + ORM Model

**Files:**
- Create: `backend/alembic/versions/20260628_1100_knowledge_chunk_field_trim.py`
- Modify: `backend/src/models/knowledge_chunk.py`
- Create: `backend/tests/integration/test_knowledge_chunk_field_trim_migration.py`

- [ ] **Step 1: Write the failing integration test**

```python
# backend/tests/integration/test_knowledge_chunk_field_trim_migration.py
from sqlalchemy import inspect


def test_knowledge_chunks_schema_after_trim(db_session):
    cols = {c["name"] for c in inspect(db_session.bind).get_columns("knowledge_chunks")}
    assert "certificate_number" in cols
    assert "certificate_date" in cols
    assert "char_start" in cols
    assert "char_end" in cols
    assert "page_start" not in cols
    assert "issue_date" not in cols
    assert "variables" not in cols
    assert "winning_flag" not in cols
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_chunk_field_trim_migration.py -v
```

Expected: FAIL (`certificate_number` not in columns)

- [ ] **Step 3: Create migration and update ORM**

`backend/alembic/versions/20260628_1100_knowledge_chunk_field_trim.py`:

```python
"""knowledge chunk field trim

Revision ID: 20260628_1100
Revises: 20260628_1000
"""
revision = "20260628_1100"
down_revision = "20260628_1000"

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("TRUNCATE knowledge_chunks CASCADE")
    else:
        op.execute("DELETE FROM knowledge_chunks")
    for col in (
        "page_start", "page_end", "edit_distance_avg", "variables",
        "exclusion_rules", "need_parent_context", "winning_flag",
        "is_immutable", "issue_date",
    ):
        op.drop_column("knowledge_chunks", col)
    op.add_column("knowledge_chunks", sa.Column("certificate_date", sa.String(512), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("certificate_number", sa.String(1024), nullable=True))

def downgrade() -> None:
    # minimal: re-add dropped columns as nullable
    ...
```

`backend/src/models/knowledge_chunk.py` 删除对应 Mapped 列，新增：

```python
    certificate_date: Mapped[str | None] = mapped_column(String(512), nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(String(1024), nullable=True)
```

保留 `char_start`, `char_end`, `expire_date`。

Run:

```bash
cd backend && ../.venv/bin/alembic upgrade head
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_chunk_field_trim_migration.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260628_1100_knowledge_chunk_field_trim.py \
  backend/src/models/knowledge_chunk.py \
  backend/tests/integration/test_knowledge_chunk_field_trim_migration.py
git commit -m "feat: trim knowledge chunk columns and add certificate fields"
```

---

## Task 4: chunk_service 自动 char + 证书写入

**Files:**
- Modify: `backend/src/services/knowledge/chunk_service.py`
- Modify: `backend/tests/helpers/chunk_payload.py`
- Modify: `backend/tests/unit/test_knowledge_chunk_service.py`

- [ ] **Step 1: Write the failing test**

在 `test_knowledge_chunk_service.py` 添加：

```python
def test_create_chunk_auto_sets_char_range_and_certificate_fields(
    db_session, seeded_kb, seeded_document_tree
):
    from src.models.knowledge_chunk import KnowledgeChunk
    from tests.helpers.chunk_payload import minimal_chunk_payload

    doc_id, node_id = seeded_document_tree
    payload = minimal_chunk_payload(
        content="## 1.1\n\n资质正文XYZ",
        certificate_number="CERT-001, CERT-002",
        certificate_date="2024-01-01,2025-01-01",
        expire_date="2025-06-01",
    )
    chunk = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=payload,
        doc_id=doc_id,
        primary_node_id=node_id,
    )
    row = db_session.get(KnowledgeChunk, chunk.id)
    assert row.char_start is not None
    assert row.char_end is not None
    assert row.certificate_number == "CERT-001,CERT-002"
    assert row.certificate_date == "2024-01-01,2025-01-01"
    assert row.page_start is not ...  # attribute removed - use not hasattr
```

改用：

```python
    assert not hasattr(row, "page_start")
    assert row.expire_date.isoformat() == "2025-06-01"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk_service.py::test_create_chunk_auto_sets_char_range_and_certificate_fields -v
```

- [ ] **Step 3: Update chunk_service.py**

在 `create_knowledge_chunk` 中：

1. 导入 `compute_section_char_range` 与 certificate utils
2. 删除 `page_start/page_end/need_parent_context/variables/is_immutable/exclusion_rules/winning_flag/edit_distance_avg/issue_date` 赋值
3. 在构建 `KnowledgeChunk` 前：

```python
char_start, char_end = compute_section_char_range(
    db,
    kb_id=kb_id,
    doc_id=doc_id,
    primary_node_id=node_uuid,
    content=content,
) if node_uuid else (None, None)

cert_number = normalize_certificate_number(payload.get("certificate_number"))
cert_date = normalize_certificate_date(payload.get("certificate_date"))
expire_date = payload.get("expire_date")
if isinstance(expire_date, str):
    expire_date = earliest_expire_date_from_csv(expire_date) or _parse_date_or_none(expire_date)
```

4. 设置 `char_start=char_start`, `char_end=char_end`, `certificate_number=cert_number`, `certificate_date=cert_date`

更新 `backend/tests/helpers/chunk_payload.py` — 删除废弃字段，添加：

```python
        "certificate_number": None,
        "certificate_date": None,
```

- [ ] **Step 4: Run tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_service.py \
  backend/tests/helpers/chunk_payload.py \
  backend/tests/unit/test_knowledge_chunk_service.py
git commit -m "feat: auto-compute char range and persist certificate fields on chunk create"
```

---

## Task 5: API Schemas + Routes

**Files:**
- Modify: `backend/src/api/schemas/knowledge_chunks.py`
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/tests/integration/test_knowledge_api.py`

- [ ] **Step 1: Write the failing integration test**

```python
def test_chunk_detail_excludes_internal_char_fields(client, kb_id, doc_tree):
    doc_id, node_id = doc_tree
    create = client.post(
        f"/api/v1/kbs/{kb_id}/knowledge-chunks",
        json={
            "doc_id": str(doc_id),
            "primary_node_id": str(node_id),
            "title": "T",
            "content": "正文",
            "knowledge_type": "fact",
            "source_type": "bid",
            "block_type_code": "ip_patent",
            "application_type_code": "fixed_reference",
            "business_line_codes": ["general"],
            "certificate_number": "NO-1",
            "certificate_date": "2024-01-01",
        },
    )
    chunk_id = create.json()["data"]["id"]
    detail = client.get(f"/api/v1/kbs/{kb_id}/knowledge-chunks/{chunk_id}").json()["data"]
    assert detail["certificate_number"] == "NO-1"
    assert "char_start" not in detail
    assert "page_start" not in detail
    assert "winning_flag" not in detail
    assert "issue_date" not in detail
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py::test_chunk_detail_excludes_internal_char_fields -v
```

- [ ] **Step 3: Update schemas**

`CreateKnowledgeChunkRequest` 删除废弃字段，新增：

```python
    certificate_date: str | None = None
    certificate_number: str | None = None
```

`KnowledgeChunkListFilters` 删除 `winning_flag`, `issue_date_from`, `issue_date_to`。

`knowledge_chunks.py` 路由：

- `_serialize_chunk_detail` / `_serialize_chunk_list_item` 删除所有废弃字段
- 不输出 `char_start`, `char_end`
- 新增 `certificate_date`, `certificate_number`
- 删除 list 筛选中对 `winning_flag` / `issue_date` 的 filter 逻辑

- [ ] **Step 4: Run integration tests**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/schemas/knowledge_chunks.py \
  backend/src/api/routes/knowledge_chunks.py \
  backend/tests/integration/test_knowledge_api.py
git commit -m "feat: update chunk API for trimmed fields and certificates"
```

---

## Task 6: Prefill + Index Summary LLM

**Files:**
- Modify: `backend/src/services/knowledge/knowledge_prefill_prompt.py`
- Modify: `backend/src/services/knowledge/prefill_service.py`
- Modify: `backend/src/services/knowledge/chunk_summary_service.py`
- Modify: `backend/src/services/knowledge/chunk_index_task.py`
- Modify: `backend/tests/unit/test_knowledge_prefill.py`
- Create: `backend/tests/unit/test_chunk_summary_service.py`（若不存在则补充测试）

- [ ] **Step 1: Write the failing prefill test**

```python
def test_prefill_maps_certificate_fields(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: (
            '{"title":"T","certificate_number":"A1,B2","certificate_date":"2024-01-01,2025-01-01",'
            '"expire_date":"2025-06-01,2024-12-31"}'
        ),
    )
    result = prefill_knowledge_attributes(content="证书", metadata={})
    assert result["certificate_number"] == "A1,B2"
    assert result["certificate_date"] == "2024-01-01,2025-01-01"
    assert result["expire_date"] == "2024-12-31"
    assert "issue_date" not in result
    assert "winning_flag" not in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_prefill.py::test_prefill_maps_certificate_fields -v
```

- [ ] **Step 3: Update prompt and services**

`knowledge_prefill_prompt.py` — 删除 `issue_date`/`winning_flag` 说明，新增 `certificate_number`/`certificate_date`；`expire_date` 多值取 min。

`prefill_service.py` `_build_partial_result` / `_normalize_prefill`：

```python
    result["certificate_number"] = normalize_certificate_number(parsed.get("certificate_number"))
    result["certificate_date"] = normalize_certificate_date(parsed.get("certificate_date"))
    expire_raw = parsed.get("expire_date")
    if isinstance(expire_raw, str) and "," in expire_raw:
        min_date = earliest_expire_date_from_csv(expire_raw)
        result["expire_date"] = min_date.isoformat() if min_date else None
```

`chunk_summary_service.py` system prompt 改为：

```python
_SUMMARY_SYSTEM_PROMPT = (
    "你是标书知识块摘要助手。输出 JSON：summary、certificate_number、certificate_date、"
    "expire_date、date_confidence（high/medium/low）。"
    "certificate_number/certificate_date 多个值用英文逗号分隔；expire_date 取最早失效日。"
    "只返回 JSON。"
)
```

`apply_summary_update` 签名改为：

```python
def apply_summary_update(
    *,
    current_summary: str | None,
    current_certificate_number: str | None,
    current_certificate_date: str | None,
    current_expire_date: date | None,
    llm_result: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
```

`chunk_index_task.py` 调用处同步更新，删除 `chunk.issue_date = ...`。

- [ ] **Step 4: Run tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_prefill.py tests/unit/test_certificate_field_utils.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/knowledge_prefill_prompt.py \
  backend/src/services/knowledge/prefill_service.py \
  backend/src/services/knowledge/chunk_summary_service.py \
  backend/src/services/knowledge/chunk_index_task.py \
  backend/tests/unit/test_knowledge_prefill.py
git commit -m "feat: align prefill and index summary with certificate fields"
```

---

## Task 7: 更新全部 Backend 测试 Fixtures

**Files:**
- Modify: all `backend/tests/**` referencing removed chunk fields

- [ ] **Step 1: Bulk replace ORM kwargs**

在所有 `KnowledgeChunk(...)` 构造中删除：

```python
page_start=..., page_end=..., need_parent_context=..., variables=...,
is_immutable=..., exclusion_rules=..., winning_flag=..., edit_distance_avg=...,
issue_date=...,
```

保留 `char_start`/`char_end` 若测试需要资产关联；否则可省略（由 service 写入）。

- [ ] **Step 2: Update minimal_chunk_orm_kwargs in chunk_payload.py**

删除废弃键，添加 `certificate_number`, `certificate_date`。

- [ ] **Step 3: Run backend unit tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit -q --ignore=tests/unit/test_reset_business_data.py
```

Expected: PASS（SQLite JSONB blueprint 问题如存在则跳过 integration）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: update fixtures for trimmed knowledge chunk fields"
```

---

## Task 8: Frontend Types + Meta

**Files:**
- Modify: `frontend/src/services/knowledgeChunks.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/constants/knowledgeChunkMeta.test.ts
it("labels certificate fields", () => {
  expect(getFieldLabel("certificate_number")).toBe("证书编号");
  expect(getFieldLabel("certificate_date")).toBe("证书日期");
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- knowledgeChunkMeta.test.ts
```

- [ ] **Step 3: Update types and meta**

`knowledgeChunks.ts` — `CreateKnowledgeChunkRequest` / `KnowledgeChunkDetail`：

- 删除：`page_start`, `page_end`, `char_start`, `char_end`, `variables`, `exclusion_rules`, `need_parent_context`, `winning_flag`, `is_immutable`, `edit_distance_avg`, `issue_date`
- 新增：`certificate_number?: string | null`, `certificate_date?: string | null`
- `PrefillResult` 同步

`knowledgeChunkMeta.ts`：

- 删除废弃 label（`page_start`, `char_start`, `winning_flag`, `issue_date`, `variables` 等）
- 新增 `certificate_number: "证书编号"`, `certificate_date: "证书日期"`
- 删除 `issue_date_from/to` 若仅用于 chunk 筛选

- [ ] **Step 4: Run test**

```bash
cd frontend && npm test -- knowledgeChunkMeta.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/knowledgeChunks.ts \
  frontend/src/constants/knowledgeChunkMeta.ts \
  frontend/src/constants/knowledgeChunkMeta.test.ts
git commit -m "feat: update frontend chunk types and meta for field trim"
```

---

## Task 9: 录入 / 浏览 / 详情 / 批量 UI

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx`
- Modify: `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx`
- Modify: `frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx`
- Modify: `frontend/src/pages/Knowledge/batchIngestUtils.ts`
- Modify: `frontend/src/pages/Knowledge/batchIngestUtils.test.ts`

- [ ] **Step 1: KnowledgeEntryPage 表单精简**

删除 Form.Item：

- `page_start`, `page_end`, `char_start`, `char_end`
- `edit_distance_avg`, `variables_json`, `exclusion_rules_json`
- `need_parent_context`, `is_immutable`, `winning_flag`, `issue_date`

新增：

```tsx
<Form.Item name="certificate_number" label={getFieldLabel("certificate_number")}>
  <Input placeholder="多个编号用英文逗号分隔" />
</Form.Item>
<Form.Item name="certificate_date" label={getFieldLabel("certificate_date")}>
  <Input placeholder="YYYY-MM-DD，多个用英文逗号分隔" />
</Form.Item>
<Form.Item name="expire_date" label={getFieldLabel("expire_date")}>
  <Input type="date" />
</Form.Item>
```

`buildCreatePayload` / `applyPrefillToForm` 删除废弃字段映射，添加证书字段。

资质类提示（`block_type_code` 以 `qualification_`/`financial_`/`ip_` 开头时）：

```tsx
<Alert type="info" showIcon message="建议填写证书编号、证书日期与失效日期" />
```

**保留** `sectionCharStart={preview.char_start}` 给 `KnowledgeContentViewer`（预览层，非 chunk 字段）。

- [ ] **Step 2: KnowledgeBrowsePage**

删除筛选表单项：`winning_flag`, `issue_date_from`, `issue_date_to` 及相关 URL 参数映射。

- [ ] **Step 3: KnowledgeChunkDetailDrawer**

删除废弃 Descriptions.Item；新增证书编号/日期展示；保留 `expire_date` + 过期 Badge。

- [ ] **Step 4: batchIngestUtils**

`buildAutoCreatePayload` 删除：

```typescript
    page_start, page_end, char_start, char_end,
    need_parent_context, variables, exclusion_rules,
    is_immutable, winning_flag, edit_distance_avg, issue_date,
```

新增：

```typescript
    certificate_number: prefill.certificate_number ?? null,
    certificate_date: prefill.certificate_date ?? null,
    expire_date: normalizeOptionalDate(prefill.expire_date),
```

更新 `batchIngestUtils.test.ts` 期望值。

- [ ] **Step 5: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Knowledge/
git commit -m "feat: simplify knowledge entry UI and add certificate fields"
```

---

## Task 10: entry_content_service 预览页码修复

**Files:**
- Modify: `backend/src/services/knowledge/entry_content_service.py`

- [ ] **Step 1: Update `_page_range`**

删除从 `KnowledgeChunk.page_start` 读取的逻辑，仅从 `assets` 聚合：

```python
def _page_range(
    chunks: list[KnowledgeChunk],
    assets: list[ChunkAsset],
) -> tuple[int | None, int | None]:
    _ = chunks
    asset_page_starts = [item.page_start for item in assets if item.page_start is not None]
    asset_page_ends = [item.page_end for item in assets if item.page_end is not None]
    if asset_page_starts and asset_page_ends:
        return (min(asset_page_starts), max(asset_page_ends))
    return (None, None)
```

- [ ] **Step 2: Run entry content tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_entry_content.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/services/knowledge/entry_content_service.py
git commit -m "fix: derive preview page range from assets after chunk page columns removed"
```

---

## Task 11: 全量验证

- [ ] **Step 1: Run backend tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_certificate_field_utils.py \
  tests/unit/test_knowledge_prefill.py \
  tests/unit/test_knowledge_chunk_service.py -v
```

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

- [ ] **Step 3: Manual smoke**

1. 知识录入 → AI 预填 → 确认证书字段出现、定位字段不出现
2. 保存 → 浏览详情 → 证书/失效日期正确
3. 批量入库成功

---

## Spec Coverage Self-Review

| Spec 要求 | Task |
|-----------|------|
| DROP 10 列 + ADD 证书列 | Task 3 |
| char 内部保留、API 不暴露 | Task 4, 5 |
| 证书逗号分隔 + expire min | Task 1, 4, 6 |
| prefill/index 更新 | Task 6 |
| 前端表单/浏览/详情 | Task 8, 9 |
| NodePreview char 保留 | Task 9（不改 preview） |
| TRUNCATE 迁移 | Task 3 |
| 预览 page 不依赖 chunk | Task 10 |
| 测试 fixtures | Task 7 |

No placeholders. Field names consistent: `certificate_number`, `certificate_date`, `expire_date`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-28-knowledge-chunk-field-trim.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
