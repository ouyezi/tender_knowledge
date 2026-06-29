# Knowledge Qualification Info Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 `qualification_info` 单一文本字段替代 `certificate_number`/`certificate_date`，统一预填与索引 LLM 契约，删除旧版 `embedding_task`，保留块级 `expire_date` 自动推导。

**Architecture:** 新增 `qualification_field_utils` 负责 `简称|编号|发证日|有效期`（`;` 分隔多条）的解析与 `expire_date` min 推导；Alembic 清库后换列；`chunk_service`/`prefill_service`/`chunk_summary_service`/`chunk_index_task` 写入前规范化；前端单字段录入展示。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest; React 18, TypeScript, Ant Design 5, Vitest.

**Design spec:** `docs/superpowers/specs/2026-06-29-knowledge-qualification-info-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/services/knowledge/qualification_field_utils.py` | 资质文本解析、规范化、`expire_date` 推导 |
| `backend/src/services/knowledge/certificate_field_utils.py` | **删除**（`parse_expire_date_value` 迁入新模块） |
| `backend/alembic/versions/20260629_1000_qualification_info.py` | TRUNCATE + DROP 证书列 + ADD `qualification_info` |
| `backend/src/models/knowledge_chunk.py` | ORM 列替换 |
| `backend/src/services/knowledge/chunk_service.py` | 创建时写入 `qualification_info` + 推导 `expire_date` |
| `backend/src/services/knowledge/chunk_summary_service.py` | 索引 LLM prompt + `apply_summary_update` |
| `backend/src/services/knowledge/chunk_index_task.py` | 索引后写入新字段 |
| `backend/src/services/knowledge/knowledge_prefill_prompt.py` | 预填 prompt 换 `qualification_info` |
| `backend/src/services/knowledge/prefill_service.py` | 预填 normalize + `date_confidence` 门槛 |
| `backend/src/api/schemas/knowledge_chunks.py` | 请求/响应 schema |
| `backend/src/api/routes/knowledge_chunks.py` | 序列化 |
| `backend/src/services/knowledge/embedding_task.py` | **删除** |
| `backend/tests/unit/test_qualification_field_utils.py` | 工具函数单测 |
| `backend/tests/unit/test_knowledge_embedding.py` | **删除** |
| `backend/tests/helpers/chunk_payload.py` | 测试 payload |
| `frontend/src/services/knowledgeChunks.ts` | TS 类型 |
| `frontend/src/constants/knowledgeChunkMeta.ts` | 字段 label |
| `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx` | 录入表单 |
| `frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx` | 详情展示 |
| `frontend/src/pages/Knowledge/batchIngestUtils.ts` | 批量导入 payload |

---

### Task 1: `qualification_field_utils` 工具函数

**Files:**
- Create: `backend/src/services/knowledge/qualification_field_utils.py`
- Create: `backend/tests/unit/test_qualification_field_utils.py`
- Delete: `backend/src/services/knowledge/certificate_field_utils.py`
- Delete: `backend/tests/unit/test_certificate_field_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_qualification_field_utils.py
from datetime import date

from src.services.knowledge.qualification_field_utils import (
    earliest_expire_date_from_qualification_info,
    format_qualification_record,
    normalize_qualification_info,
    parse_expire_date_value,
    parse_qualification_records,
)


def test_normalize_qualification_info_dedupes_records():
    raw = (
        "ISO9001|A001|2024-01-01|2026-12-31;"
        " ISO9001|A001|2024-01-01|2026-12-31 ;"
        "软件著作权|2020SR123|2020-06-01|2030-06-01"
    )
    assert normalize_qualification_info(raw) == (
        "ISO9001|A001|2024-01-01|2026-12-31;"
        "软件著作权|2020SR123|2020-06-01|2030-06-01"
    )


def test_parse_qualification_records_splits_pipe_fields():
    records = parse_qualification_records(
        "ISO9001|A001|2024-01-01|2026-12-31;营业执照||2024-02-01|长期有效"
    )
    assert len(records) == 2
    assert records[0].name == "ISO9001"
    assert records[0].number == "A001"
    assert records[0].issue_date == "2024-01-01"
    assert records[0].expire_text == "2026-12-31"
    assert records[1].expire_text == "长期有效"


def test_earliest_expire_date_from_qualification_info_picks_min():
    text = "ISO9001|A001|2024-01-01|2026-12-31;软著|SR1|2020-06-01|2024-06-01"
    assert earliest_expire_date_from_qualification_info(text) == date(2024, 6, 1)


def test_earliest_expire_date_ignores_non_iso_expire_text():
    assert earliest_expire_date_from_qualification_info("营业执照||2024-01-01|长期有效") is None


def test_format_qualification_record():
    assert format_qualification_record(
        name="ISO9001", number="A001", issue_date="2024-01-01", expire_text="2026-12-31"
    ) == "ISO9001|A001|2024-01-01|2026-12-31"


def test_parse_expire_date_value():
    assert parse_expire_date_value("2025-06-01") == date(2025, 6, 1)
    assert parse_expire_date_value(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_qualification_field_utils.py -v`

Expected: FAIL `ModuleNotFoundError: qualification_field_utils`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/knowledge/qualification_field_utils.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class QualificationRecord:
    name: str
    number: str
    issue_date: str
    expire_text: str


def _parse_iso_date(value: str) -> date | None:
    if not _ISO_DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_iso_segment(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return text if _parse_iso_date(text) else ""


def _split_record(raw: str) -> QualificationRecord | None:
    parts = [part.strip() for part in raw.split("|")]
    while len(parts) < 4:
        parts.append("")
    name, number, issue_date, expire_text = parts[:4]
    if not any((name, number, issue_date, expire_text)):
        return None
    return QualificationRecord(
        name=name,
        number=number,
        issue_date=_normalize_iso_segment(issue_date),
        expire_text=expire_text.strip(),
    )


def format_qualification_record(
    *,
    name: str,
    number: str,
    issue_date: str,
    expire_text: str,
) -> str:
    return "|".join(
        (
            name.strip(),
            number.strip(),
            _normalize_iso_segment(issue_date),
            expire_text.strip(),
        )
    )


def parse_qualification_records(value: str | None) -> list[QualificationRecord]:
    if not value:
        return []
    records: list[QualificationRecord] = []
    for raw in str(value).split(";"):
        record = _split_record(raw)
        if record is not None:
            records.append(record)
    return records


def normalize_qualification_info(value: str | None) -> str | None:
    if not value:
        return None
    seen: set[str] = set()
    normalized: list[str] = []
    for record in parse_qualification_records(value):
        formatted = format_qualification_record(
            name=record.name,
            number=record.number,
            issue_date=record.issue_date,
            expire_text=record.expire_text,
        )
        if formatted in seen:
            continue
        seen.add(formatted)
        normalized.append(formatted)
    if not normalized:
        return None
    result = ";".join(normalized)
    return result[:2048] if len(result) > 2048 else result


def earliest_expire_date_from_qualification_info(value: str | None) -> date | None:
    dates: list[date] = []
    for record in parse_qualification_records(value):
        parsed = _parse_iso_date(record.expire_text)
        if parsed is not None:
            dates.append(parsed)
    return min(dates) if dates else None


def parse_expire_date_value(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if "," in text:
        dates = [_parse_iso_date(part.strip()) for part in text.split(",")]
        parsed = [item for item in dates if item is not None]
        return min(parsed) if parsed else None
    return _parse_iso_date(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_qualification_field_utils.py -v`

Expected: PASS (6 tests)

- [ ] **Step 5: Remove old certificate utils**

Delete `backend/src/services/knowledge/certificate_field_utils.py` and `backend/tests/unit/test_certificate_field_utils.py`.

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_qualification_field_utils.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/knowledge/qualification_field_utils.py \
  backend/tests/unit/test_qualification_field_utils.py
git rm backend/src/services/knowledge/certificate_field_utils.py \
  backend/tests/unit/test_certificate_field_utils.py
git commit -m "feat: add qualification_field_utils for merged cert text field"
```

---

### Task 2: Alembic migration + ORM model

**Files:**
- Create: `backend/alembic/versions/20260629_1000_qualification_info.py`
- Modify: `backend/src/models/knowledge_chunk.py`
- Modify: `backend/tests/integration/test_knowledge_chunk_field_trim_migration.py`

- [ ] **Step 1: Write the failing integration test**

Replace assertions in `backend/tests/integration/test_knowledge_chunk_field_trim_migration.py`:

```python
from sqlalchemy import inspect


def test_knowledge_chunks_schema_after_qualification_info(db_session):
    cols = {c["name"] for c in inspect(db_session.bind).get_columns("knowledge_chunks")}
    assert "qualification_info" in cols
    assert "certificate_number" not in cols
    assert "certificate_date" not in cols
    assert "expire_date" in cols
    assert "char_start" in cols
    assert "char_end" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_chunk_field_trim_migration.py -v`

Expected: FAIL (`qualification_info` not in cols or `certificate_number` still present)

- [ ] **Step 3: Add migration**

```python
# backend/alembic/versions/20260629_1000_qualification_info.py
"""knowledge chunk qualification_info

Revision ID: 20260629_1000
Revises: 20260628_1200
Create Date: 2026-06-29 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260629_1000"
down_revision: str | None = "20260628_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("TRUNCATE knowledge_chunks CASCADE")
    else:
        op.execute("DELETE FROM knowledge_chunks")

    op.drop_column("knowledge_chunks", "certificate_number")
    op.drop_column("knowledge_chunks", "certificate_date")
    op.add_column(
        "knowledge_chunks",
        sa.Column("qualification_info", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "qualification_info")
    op.add_column(
        "knowledge_chunks",
        sa.Column("certificate_number", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("certificate_date", sa.String(length=512), nullable=True),
    )
```

- [ ] **Step 4: Update ORM model**

In `backend/src/models/knowledge_chunk.py`, replace:

```python
certificate_number: Mapped[str | None] = mapped_column(String(1024), nullable=True)
certificate_date: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

with:

```python
qualification_info: Mapped[str | None] = mapped_column(String(2048), nullable=True)
```

- [ ] **Step 5: Run migration in test DB and re-run test**

Run: `cd backend && ../.venv/bin/alembic upgrade head`

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_chunk_field_trim_migration.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/20260629_1000_qualification_info.py \
  backend/src/models/knowledge_chunk.py \
  backend/tests/integration/test_knowledge_chunk_field_trim_migration.py
git commit -m "feat: migrate knowledge_chunks to qualification_info column"
```

---

### Task 3: `chunk_service` 创建路径

**Files:**
- Modify: `backend/src/services/knowledge/chunk_service.py`
- Modify: `backend/tests/unit/test_knowledge_chunk_service.py`
- Modify: `backend/tests/helpers/chunk_payload.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/test_knowledge_chunk_service.py`, replace certificate test with:

```python
def test_create_knowledge_chunk_normalizes_qualification_info_and_expire_date(
    db_session, seeded_kb, seeded_doc, seeded_heading_node
):
    from src.services.knowledge.chunk_service import create_knowledge_chunk

    chunk = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={
            **minimal_chunk_payload(),
            "qualification_info": (
                "ISO9001|A001|2024-01-01|2026-12-31;"
                "软著|SR1|2020-06-01|2024-06-01"
            ),
        },
        doc_id=seeded_doc.document_id,
        primary_node_id=seeded_heading_node.node_id,
    )
    assert chunk.qualification_info == (
        "ISO9001|A001|2024-01-01|2026-12-31;软著|SR1|2020-06-01|2024-06-01"
    )
    assert chunk.expire_date.isoformat() == "2024-06-01"
```

Update `backend/tests/helpers/chunk_payload.py`:

```python
"qualification_info": None,
```

(remove `certificate_number` / `certificate_date` keys)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk_service.py::test_create_knowledge_chunk_normalizes_qualification_info_and_expire_date -v`

Expected: FAIL (attribute or TypeError on `certificate_number`)

- [ ] **Step 3: Implement in chunk_service**

Replace certificate imports/usage in `backend/src/services/knowledge/chunk_service.py`:

```python
from src.services.knowledge.qualification_field_utils import (
    earliest_expire_date_from_qualification_info,
    normalize_qualification_info,
    parse_expire_date_value,
)
```

Replace cert handling before `KnowledgeChunk(...)`:

```python
qualification_info = normalize_qualification_info(payload.get("qualification_info"))
expire_date = parse_expire_date_value(payload.get("expire_date"))
if qualification_info and expire_date is None:
    expire_date = earliest_expire_date_from_qualification_info(qualification_info)
```

In `KnowledgeChunk(...)` kwargs:

```python
qualification_info=qualification_info,
expire_date=expire_date,
```

(remove `certificate_number` / `certificate_date`)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_service.py \
  backend/tests/unit/test_knowledge_chunk_service.py \
  backend/tests/helpers/chunk_payload.py
git commit -m "feat: persist qualification_info on knowledge chunk create"
```

---

### Task 4: `chunk_summary_service` 索引 LLM 契约

**Files:**
- Modify: `backend/src/services/knowledge/chunk_summary_service.py`
- Modify: `backend/tests/unit/test_chunk_summary_service.py`

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/unit/test_chunk_summary_service.py` entirely:

```python
from datetime import date

from src.services.knowledge.chunk_summary_service import apply_summary_update


def test_apply_summary_update_high_confidence_qualification_info():
    chunk_fields, warnings = apply_summary_update(
        current_summary="旧摘要",
        current_qualification_info=None,
        current_expire_date=None,
        llm_result={
            "summary": "新摘要",
            "qualification_info": "ISO9001|NO-1|2023-01-01|2026-01-01",
            "date_confidence": "high",
        },
    )
    assert chunk_fields["summary"] == "新摘要"
    assert chunk_fields["qualification_info"] == "ISO9001|NO-1|2023-01-01|2026-01-01"
    assert chunk_fields["expire_date"].isoformat() == "2026-01-01"
    assert not warnings


def test_apply_summary_update_low_confidence_keeps_qualification_info():
    chunk_fields, _ = apply_summary_update(
        current_summary="旧",
        current_qualification_info="KEEP|K1|2020-01-01|2025-01-01",
        current_expire_date=date(2025, 1, 1),
        llm_result={
            "summary": "新",
            "qualification_info": "NEW|N1|2023-01-01|2028-01-01",
            "date_confidence": "low",
        },
    )
    assert chunk_fields["summary"] == "新"
    assert chunk_fields["qualification_info"] == "KEEP|K1|2020-01-01|2025-01-01"
    assert chunk_fields["expire_date"].isoformat() == "2025-01-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_summary_service.py -v`

Expected: FAIL (`unexpected keyword argument 'current_qualification_info'`)

- [ ] **Step 3: Update chunk_summary_service**

Replace `_SUMMARY_SYSTEM_PROMPT`:

```python
_SUMMARY_SYSTEM_PROMPT = (
    "你是标书知识块摘要助手。输出 JSON：summary、qualification_info、date_confidence（high/medium/low）。"
    "qualification_info 格式：每条资质为 简称|编号|发证日期|有效期，多条用英文分号分隔；"
    "发证日期与有效期中的日期使用 YYYY-MM-DD；有效期可为长期有效等非日期文本。"
    "结合正文与图片信息提取或修正资质；information_role=core 的证书/资质图应写入 qualification_info；"
    "information_role=auxiliary 的图忽略。只返回 JSON，不要 markdown。"
)
```

Replace imports with `qualification_field_utils`.

Replace `apply_summary_update` signature and body:

```python
def apply_summary_update(
    *,
    current_summary: str | None,
    current_qualification_info: str | None,
    current_expire_date: date | None,
    llm_result: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    summary = str(llm_result.get("summary") or "").strip()
    if not summary:
        summary = current_summary or ""
        warnings.append("summary_rewrite_empty")

    fields: dict[str, Any] = {"summary": summary}
    date_confidence = str(llm_result.get("date_confidence") or "").strip().lower()
    if date_confidence == "high":
        normalized = normalize_qualification_info(llm_result.get("qualification_info"))
        fields["qualification_info"] = (
            normalized if normalized is not None else current_qualification_info
        )
        derived = earliest_expire_date_from_qualification_info(fields["qualification_info"])
        fields["expire_date"] = derived if derived is not None else current_expire_date
    else:
        fields["qualification_info"] = current_qualification_info
        fields["expire_date"] = current_expire_date

    return fields, warnings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_summary_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_summary_service.py \
  backend/tests/unit/test_chunk_summary_service.py
git commit -m "feat: index summary LLM writes qualification_info with confidence gate"
```

---

### Task 5: `chunk_index_task` 字段接线

**Files:**
- Modify: `backend/src/services/knowledge/chunk_index_task.py`
- Modify: `backend/tests/unit/test_chunk_index_task.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_chunk_index_task.py`:

```python
def test_index_knowledge_chunk_updates_qualification_info_on_high_confidence(
    db_session, seeded_kb, monkeypatch
):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)

    monkeypatch.setattr(
        "src.services.knowledge.chunk_index_task.rewrite_chunk_summary",
        lambda **_: {
            "summary": "新摘要",
            "qualification_info": "ISO9001|A001|2024-01-01|2026-12-31",
            "date_confidence": "high",
        },
    )
    monkeypatch.setattr(
        "src.services.knowledge.chunk_index_task.EmbeddingClient.embed_text",
        lambda _self, _text: EmbeddingResult(vector=[0.1, 0.2, 0.3]),
    )
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://embedding.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    status = index_knowledge_chunk(db_session, chunk.id)

    assert status == "ready"
    db_session.refresh(chunk)
    assert chunk.qualification_info == "ISO9001|A001|2024-01-01|2026-12-31"
    assert chunk.expire_date.isoformat() == "2026-12-31"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_index_task.py::test_index_knowledge_chunk_updates_qualification_info_on_high_confidence -v`

Expected: FAIL (`qualification_info` is None)

- [ ] **Step 3: Update chunk_index_task apply block**

In `backend/src/services/knowledge/chunk_index_task.py`, replace `apply_summary_update` call:

```python
fields, warnings = apply_summary_update(
    current_summary=chunk.summary,
    current_qualification_info=chunk.qualification_info,
    current_expire_date=chunk.expire_date,
    llm_result=llm_result,
)
chunk.summary = fields["summary"]
chunk.qualification_info = fields["qualification_info"]
chunk.expire_date = fields["expire_date"]
```

(remove `certificate_number` / `certificate_date` assignments)

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_index_task.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_index_task.py \
  backend/tests/unit/test_chunk_index_task.py
git commit -m "feat: chunk index task persists qualification_info from LLM"
```

---

### Task 6: 预填 prompt + `prefill_service`

**Files:**
- Modify: `backend/src/services/knowledge/knowledge_prefill_prompt.py`
- Modify: `backend/src/services/knowledge/prefill_service.py`
- Modify: `backend/tests/unit/test_knowledge_prefill.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/test_knowledge_prefill.py`, add:

```python
def test_normalize_prefill_high_confidence_qualification_info():
    from src.services.knowledge.prefill_service import _normalize_prefill

    result = _normalize_prefill(
        {
            "summary": "摘要",
            "qualification_info": "ISO9001|A001|2024-01-01|2026-12-31",
            "date_confidence": "high",
        },
        {},
    )
    assert result["qualification_info"] == "ISO9001|A001|2024-01-01|2026-12-31"
    assert result["expire_date"] == "2026-12-31"


def test_normalize_prefill_low_confidence_skips_qualification_info():
    from src.services.knowledge.prefill_service import _normalize_prefill

    result = _normalize_prefill(
        {
            "qualification_info": "NEW|N1|2023-01-01|2028-01-01",
            "date_confidence": "low",
        },
        {},
    )
    assert result["qualification_info"] is None
    assert result["expire_date"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_prefill.py::test_normalize_prefill_high_confidence_qualification_info -v`

Expected: FAIL

- [ ] **Step 3: Update prefill_service**

In `backend/src/services/knowledge/prefill_service.py`:

- Import from `qualification_field_utils`
- `_build_partial_result`: replace `certificate_number`/`certificate_date` with `qualification_info: None`
- `_normalize_prefill`: replace certificate lines with:

```python
date_confidence = str(parsed.get("date_confidence") or "").strip().lower()
if date_confidence == "high":
    result["qualification_info"] = normalize_qualification_info(
        parsed.get("qualification_info")
    )
    derived = earliest_expire_date_from_qualification_info(result["qualification_info"])
    result["expire_date"] = derived.isoformat() if derived else None
else:
    result["qualification_info"] = None
    result["expire_date"] = None
```

In `backend/src/services/knowledge/knowledge_prefill_prompt.py`, replace certificate field lines (~28-29) with:

```python
- qualification_info: 资质/证书/授权信息；格式 简称|编号|发证日期|有效期，多条用英文分号分隔
- date_confidence: high|medium|low；仅 high 时 qualification_info 才会入库
- expire_date: 由 qualification_info 有效期自动推导，无需单独填写
```

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_prefill.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/knowledge_prefill_prompt.py \
  backend/src/services/knowledge/prefill_service.py \
  backend/tests/unit/test_knowledge_prefill.py
git commit -m "feat: prefill outputs qualification_info with confidence gate"
```

---

### Task 7: API schema + routes

**Files:**
- Modify: `backend/src/api/schemas/knowledge_chunks.py`
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/tests/integration/test_knowledge_api.py`

- [ ] **Step 1: Write the failing integration test**

In `backend/tests/integration/test_knowledge_api.py`, update create/detail assertions:

```python
"qualification_info": "ISO9001|NO-1|2024-01-01|2026-01-01",
...
assert detail["qualification_info"] == "ISO9001|NO-1|2024-01-01|2026-01-01"
```

(remove `certificate_number` / `certificate_date` from payload/assertions)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py -k qualification -v`

Expected: FAIL

- [ ] **Step 3: Update schema and routes**

In `backend/src/api/schemas/knowledge_chunks.py`, replace:

```python
certificate_number: str | None = None
certificate_date: str | None = None
```

with:

```python
qualification_info: str | None = None
```

In `backend/src/api/routes/knowledge_chunks.py` `_serialize_chunk_detail`:

```python
"qualification_info": row.qualification_info,
```

(remove certificate fields)

- [ ] **Step 4: Run integration tests**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py -v`

Expected: PASS (fix any remaining certificate references in same file)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/schemas/knowledge_chunks.py \
  backend/src/api/routes/knowledge_chunks.py \
  backend/tests/integration/test_knowledge_api.py
git commit -m "feat: expose qualification_info in knowledge chunk API"
```

---

### Task 8: 删除旧版 `embedding_task`

**Files:**
- Delete: `backend/src/services/knowledge/embedding_task.py`
- Delete: `backend/tests/unit/test_knowledge_embedding.py`

- [ ] **Step 1: Verify no production imports remain**

Run: `cd backend && rg "embedding_task|embed_knowledge_chunk|get_embedding_status" src --glob '*.py'`

Expected: no matches (only deleted files had them)

- [ ] **Step 2: Delete files**

```bash
git rm backend/src/services/knowledge/embedding_task.py \
  backend/tests/unit/test_knowledge_embedding.py
```

- [ ] **Step 3: Run full backend unit suite**

Run: `cd backend && ../.venv/bin/pytest tests/unit -q`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove legacy embedding_task for knowledge chunks"
```

---

### Task 9: 同步剩余后端测试

**Files:**
- Modify: any test still referencing `certificate_number` / `certificate_date`

- [ ] **Step 1: Find stale references**

Run: `cd backend && rg "certificate_number|certificate_date" tests src --glob '*.py'`

- [ ] **Step 2: Update each file**

Common files to check:

- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/unit/test_knowledge_prefill_context.py`
- `backend/tests/contract/test_file_import_delete.py`
- `backend/tests/unit/test_chunk_search_service.py` (ORM kwargs only)

Replace ORM/payload fields with `qualification_info`.

- [ ] **Step 3: Run full backend test suite**

Run: `cd backend && ../.venv/bin/pytest -q`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests
git commit -m "test: update backend tests for qualification_info field"
```

---

### Task 10: 前端类型与元数据

**Files:**
- Modify: `frontend/src/services/knowledgeChunks.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.test.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/src/constants/knowledgeChunkMeta.test.ts`, add:

```typescript
it("labels qualification_info", () => {
  expect(getFieldLabel("qualification_info")).toBe("资质信息");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- knowledgeChunkMeta.test.ts`

Expected: FAIL

- [ ] **Step 3: Update types and labels**

In `frontend/src/services/knowledgeChunks.ts`, replace certificate fields:

```typescript
qualification_info?: string | null;
```

In `frontend/src/constants/knowledgeChunkMeta.ts`:

```typescript
qualification_info: "资质信息",
```

(remove `certificate_number` / `certificate_date` labels)

- [ ] **Step 4: Run test**

Run: `cd frontend && npm test -- knowledgeChunkMeta.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/knowledgeChunks.ts \
  frontend/src/constants/knowledgeChunkMeta.ts \
  frontend/src/constants/knowledgeChunkMeta.test.ts
git commit -m "feat: frontend types and labels for qualification_info"
```

---

### Task 11: 前端录入、详情、批量导入

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx`
- Modify: `frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx`
- Modify: `frontend/src/pages/Knowledge/batchIngestUtils.ts`
- Modify: `frontend/src/pages/Knowledge/batchIngestUtils.test.ts`

- [ ] **Step 1: Write the failing batch ingest test**

In `frontend/src/pages/Knowledge/batchIngestUtils.test.ts`, update payload expectation:

```typescript
expect(payload.qualification_info).toBe("ISO9001|A001|2024-01-01|2026-12-31");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- batchIngestUtils.test.ts`

Expected: FAIL

- [ ] **Step 3: Update Entry page**

In `KnowledgeEntryPage.tsx`:

- Replace form state type fields `certificate_number`/`certificate_date` with `qualification_info?: string`
- Prefill mapping: `qualification_info: result.qualification_info ?? undefined`
- Submit payload: `qualification_info: values.qualification_info?.trim() || null`
- Replace two `Form.Item` with one:

```tsx
<Form.Item
  name="qualification_info"
  label={getFieldLabel("qualification_info")}
  extra="格式：简称|编号|发证日期|有效期；多条用分号分隔"
>
  <Input.TextArea rows={3} placeholder="ISO9001|A001|2024-01-01|2026-12-31" />
</Form.Item>
```

In `KnowledgeChunkDetailDrawer.tsx`, replace two certificate `Descriptions.Item` with:

```tsx
<Descriptions.Item label={getFieldLabel("qualification_info")}>
  {(detail.qualification_info || "-")
    .split(";")
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n") || "-"}
</Descriptions.Item>
```

(use `whiteSpace: "pre-wrap"` style if rendering multiline)

In `batchIngestUtils.ts`, map `qualification_info` instead of certificate fields.

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test -- batchIngestUtils.test.ts knowledgeChunkMeta.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx \
  frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx \
  frontend/src/pages/Knowledge/batchIngestUtils.ts \
  frontend/src/pages/Knowledge/batchIngestUtils.test.ts
git commit -m "feat: knowledge UI for qualification_info field"
```

---

### Task 12: 端到端验证

**Files:**
- (no new files)

- [ ] **Step 1: Run backend full suite**

Run: `cd backend && ../.venv/bin/pytest -q`

Expected: all pass

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm test -- --run`

Expected: all pass

- [ ] **Step 3: Smoke check API**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_flow.py -v`

Expected: PASS

- [ ] **Step 4: Verify no stale references**

Run: `rg "certificate_number|certificate_date|embedding_task" backend frontend --glob '*.{py,ts,tsx}'`

Expected: no matches (except migration downgrade or design docs)

- [ ] **Step 5: Commit (if any fixups)**

```bash
git add -A
git commit -m "chore: qualification_info rollout verification fixups"
```

---

## Spec Coverage Self-Review

| Spec § | Task |
|--------|------|
| 删除 embedding_task | Task 8 |
| qualification_info 字段 | Task 1–2 |
| expire_date min 推导 | Task 1, 3–6 |
| 清库迁移 | Task 2 |
| 预填 LLM 契约 | Task 6 |
| 索引 LLM + Vision | Task 4–5 |
| date_confidence 门槛 | Task 4, 6 |
| API/前端 | Task 7, 10–11 |
| 测试覆盖 | All tasks |
| 不在范围项 | 未列入任务（符合 spec） |

**Placeholder scan:** 无 TBD/TODO。  
**Type consistency:** `apply_summary_update` 参数在 Task 4–5 一致；`qualification_info` 命名全栈统一。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-29-knowledge-qualification-info.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间做 review，迭代快

**2. Inline Execution** — 在本会话用 executing-plans 按 Task 批量执行，检查点暂停确认

你想用哪种方式？
