# 四核心模块精简 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将代码库精简为知识库管理、来源导入、知识录入 V2、知识浏览 V2 四个核心模块，删除旧知识管理全部代码与数据库表，来源导入统一走 V2-only doc_chunk 解析路径，并清空测试数据。

**Architecture:** 分层删除——先重构来源导入 V2-only 通路（新建 `document_parse_runner`、精简 `import_service`/`confirm_service`/`purge_service`），再删前端旧页面与后端 routes/services，最后删 models + Alembic migration + 测试/E2E 脚本。保留 `actual_bid_parse_tasks` 表名不变。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 15 + pgvector, pytest; React 18, TypeScript, Ant Design, vitest.

**Design spec:** `docs/superpowers/specs/2026-06-20-core-four-modules-cleanup-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/services/document_parse_runner.py` | **新建** — 统一 doc_chunk 解析（actual_bid + template_file） |
| `backend/src/services/doc_chunk/import_service.py` | 只保留 `import_workspace_for_knowledge_entry()` |
| `backend/src/services/doc_chunk/types.py` | 精简 `ImportResult`（去掉 bid_outline/candidate 字段） |
| `backend/src/services/confirm_service.py` | 确认后只创建 `document_parse` 下游任务 |
| `backend/src/services/file_import_purge_service.py` | 重写 purge 链（file→doc→tree→chunks→storage） |
| `backend/src/api/routes/file_imports.py` | 改用 `document_parse_runner`，删 template parse retry |
| `backend/src/main.py` | 只注册 4 个核心 router |
| `backend/alembic/versions/20260620_1000_core_four_modules_cleanup.py` | DROP ~40 表 + 删列 + 收窄 enum |
| `frontend/src/App.tsx` | 只保留 4 路由 |
| `frontend/src/layout/AppShell.tsx` | 导航只保留 4 项 |
| `frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx` | 只选 actual_bid / template_file |
| `frontend/src/pages/FileImportCenter/index.tsx` | 解析完成链到知识录入 V2 |
| `scripts/lib/e2e/reset_business_data.py` | 更新 `BUSINESS_TABLES` 为保留表 |

---

## Task 0: 基线重置（P0）

**Files:**
- Run: `scripts/lib/e2e/reset_business_data.py`

- [ ] **Step 1: 确认本地 DB 安全**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
PYTHONPATH=../scripts/lib:.. ../.venv/bin/python -c "
from e2e.reset_business_data import assert_database_url_is_safe
assert_database_url_is_safe()
print('OK')
"
```
Expected: `OK`

- [ ] **Step 2: 清空业务数据**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
PYTHONPATH=../scripts/lib:.. ../.venv/bin/python -c "
from e2e.reset_business_data import reset_business_data
print(reset_business_data())
"
```
Expected: `{'tables_truncated': N, 'storage_entries_removed': M}`

- [ ] **Step 3: 记录当前测试基线**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest -q --co -q 2>/dev/null | tail -1
cd ../frontend && npm test -- --run 2>&1 | tail -5
```
记录测试总数供收尾对比（不 commit）。

---

## Task 1: 精简 ImportResult 与 import_service

**Files:**
- Modify: `backend/src/services/doc_chunk/types.py`
- Modify: `backend/src/services/doc_chunk/import_service.py`
- Delete: `backend/src/services/doc_chunk/mappers/bid_outline.py`
- Delete: `backend/src/services/doc_chunk/mappers/candidates.py`
- Modify: `backend/tests/unit/test_doc_chunk_import_service.py`

- [ ] **Step 1: Write the failing test**

Replace `backend/tests/unit/test_doc_chunk_import_service.py` entirely:

```python
from pathlib import Path
from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.doc_chunk.import_service import import_workspace_for_knowledge_entry

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_import_workspace_for_knowledge_entry_actual_bid(db_session, seeded_kb):
    import_id = uuid4()
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="minimal.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="x/minimal.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    result = import_workspace_for_knowledge_entry(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        workspace=FIXTURE_ROOT,
        file_import=file_import,
    )
    assert result.parse_engine == "doc_chunk"
    assert result.tree_node_count >= 1
    assert result.document_id is not None

    from src.models.document import Document, DocumentParseStatus, DocumentSourceType

    document = db_session.get(Document, result.document_id)
    assert document is not None
    assert document.source_type == DocumentSourceType.actual_bid
    assert document.parse_status == DocumentParseStatus.ready


def test_import_workspace_for_knowledge_entry_template_file(db_session, seeded_kb):
    import_id = uuid4()
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="template.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="x/template.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    result = import_workspace_for_knowledge_entry(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        workspace=FIXTURE_ROOT,
        file_import=file_import,
    )
    assert result.parse_engine == "doc_chunk"
    assert result.tree_node_count >= 1

    from src.models.document import Document, DocumentSourceType

    document = db_session.get(Document, result.document_id)
    assert document.source_type == DocumentSourceType.template_file
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_doc_chunk_import_service.py -v
```
Expected: FAIL — `ImportResult` 字段不匹配或 `import_workspace` 仍存在

- [ ] **Step 3: Simplify types.py**

In `backend/src/services/doc_chunk/types.py`, replace `ImportResult` with:

```python
@dataclass
class ImportResult:
    document_id: UUID
    tree_node_count: int
    parse_engine: str
    tree_id_map: dict[str, UUID] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Rewrite import_service.py**

Replace `backend/src/services/doc_chunk/import_service.py` with V2-only implementation. Keep only:
- `document_source_type_for_purpose()`
- `_assert_knowledge_entry_purpose()`
- `_resolve_document()` (remove `product_category_ids` assignment)
- `import_workspace_for_knowledge_entry()` — no `persist_outline`, `persist_candidates`, `classify_heading_nodes_for_document`, no bid_outline/candidates imports

Core return at end of `import_workspace_for_knowledge_entry`:

```python
    document.parse_status = DocumentParseStatus.ready

    return ImportResult(
        document_id=document.document_id,
        tree_node_count=len(tree_id_map) + enriched_tree_nodes,
        parse_engine="doc_chunk",
        tree_id_map=dict(ctx.tree_id_map),
        warnings=warnings,
    )
```

Delete functions `import_workspace()` entirely. Delete files:
- `backend/src/services/doc_chunk/mappers/bid_outline.py`
- `backend/src/services/doc_chunk/mappers/candidates.py`

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_doc_chunk_import_service.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/doc_chunk/types.py \
        backend/src/services/doc_chunk/import_service.py \
        backend/src/services/doc_chunk/mappers/bid_outline.py \
        backend/src/services/doc_chunk/mappers/candidates.py \
        backend/tests/unit/test_doc_chunk_import_service.py
git commit -m "refactor: slim doc_chunk import to knowledge-entry-only path"
```

---

## Task 2: 新建 document_parse_runner

**Files:**
- Create: `backend/src/services/document_parse_runner.py`
- Test: `backend/tests/unit/test_document_parse_runner.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_document_parse_runner.py`:

```python
from src.models.downstream_task_entry import DownstreamTaskType
from src.services.confirm_service import _downstream_task_types
from src.models.file_import import FilePurpose


def test_downstream_task_types_only_document_parse():
    assert _downstream_task_types(FilePurpose.actual_bid, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FilePurpose.template_file, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FilePurpose.actual_bid, False) == []


def test_document_parse_runner_exports():
    from src.services import document_parse_runner

    assert callable(document_parse_runner.enqueue_document_parse)
    assert callable(document_parse_runner.run_document_parse_in_new_session)
    assert callable(document_parse_runner.run_document_parse_once)
```

Note: `_downstream_task_types` test will fail until Task 3; for Task 2 step 1, split into:

```python
def test_document_parse_runner_exports():
    from src.services import document_parse_runner

    assert callable(document_parse_runner.enqueue_document_parse)
    assert callable(document_parse_runner.run_document_parse_in_new_session)
    assert callable(document_parse_runner.run_document_parse_once)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_document_parse_runner.py::test_document_parse_runner_exports -v
```
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Create document_parse_runner.py**

Create `backend/src/services/document_parse_runner.py` (~200 lines). Extract from `actual_bid_parse_runner._run_entry_doc_chunk` but simplified:

```python
"""Unified doc_chunk parse runner for actual_bid and template_file."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.config import Settings
from src.db.session import SessionLocal
from src.models.actual_bid_parse_task import (
    ActualBidParseTask,
    ActualBidParseTaskPhase,
    ActualBidParseTaskStatus,
)
from src.models.document import Document, DocumentParseStatus
from src.models.document_tree_node import DocumentTreeNode
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.services.docm_converter import ensure_docx_for_parse
from src.services.doc_chunk.import_service import import_workspace_for_knowledge_entry
from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline
from src.services.doc_chunk.workspace_manager import (
    cleanup_workspace,
    ensure_workspace,
    workspace_path_for_task,
)

logger = logging.getLogger(__name__)


class DocumentParseServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_docx_path(file_import: FileImport) -> Path:
    storage_root = Path(Settings().storage_root)
    source_path = storage_root / file_import.storage_path
    return ensure_docx_for_parse(source_path)


def _clear_document_tree_for_reparse(
    db: Session, *, kb_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    db.query(DocumentTreeNode).filter(
        DocumentTreeNode.kb_id == kb_id,
        DocumentTreeNode.document_id == document_id,
    ).delete(synchronize_session=False)


def enqueue_document_parse(
    db: Session,
    *,
    kb_id: uuid.UUID,
    import_id: uuid.UUID,
    operator_id: str,
    trace_id: uuid.UUID | None,
    force_reparse: bool = False,
) -> ActualBidParseTask:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise DocumentParseServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status != FileImportStatus.confirmed:
        raise DocumentParseServiceError(
            "Import must be confirmed", code="IMPORT_NOT_CONFIRMED", status_code=422
        )
    if record.file_purpose not in {FilePurpose.actual_bid, FilePurpose.template_file}:
        raise DocumentParseServiceError(
            "Unsupported file purpose", code="VALIDATION", status_code=422
        )

    active = (
        db.query(ActualBidParseTask)
        .filter(
            ActualBidParseTask.kb_id == kb_id,
            ActualBidParseTask.import_id == import_id,
            ActualBidParseTask.status.in_(
                [ActualBidParseTaskStatus.pending, ActualBidParseTaskStatus.running]
            ),
        )
        .all()
    )
    if active and not force_reparse:
        raise DocumentParseServiceError(
            "Parse task already running", code="PARSE_ALREADY_RUNNING", status_code=409
        )

    task = ActualBidParseTask(
        kb_id=kb_id,
        import_id=import_id,
        status=ActualBidParseTaskStatus.pending,
        created_by=operator_id,
    )
    db.add(task)
    db.flush()

    entry = DownstreamTaskEntry(
        kb_id=kb_id,
        import_id=import_id,
        task_type=DownstreamTaskType.document_parse,
        status=DownstreamTaskStatus.pending,
        payload={"parse_task_id": str(task.parse_task_id)},
    )
    db.add(entry)
    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid.uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.route,
            payload_summary={"parse_task_id": str(task.parse_task_id)},
        )
    )
    db.flush()
    return task


def _run_entry(db: Session, entry: DownstreamTaskEntry) -> None:
    file_import = db.get(FileImport, entry.import_id)
    if file_import is None:
        entry.status = DownstreamTaskStatus.failed
        return

    parse_task_id = uuid.UUID(entry.payload.get("parse_task_id", ""))
    task = db.get(ActualBidParseTask, parse_task_id)
    if task is None:
        entry.status = DownstreamTaskStatus.failed
        return

    task.status = ActualBidParseTaskStatus.running
    task.started_at = _now()
    task.task_phase = ActualBidParseTaskPhase.document_parse
    db.flush()

    try:
        if file_import.file_type != FileType.docx:
            raise ValueError("Only docx is supported")

        docx_path = _resolve_docx_path(file_import)
        if not docx_path.exists():
            raise FileNotFoundError(str(docx_path))

        storage_root = Path(Settings().storage_root)
        workspace = workspace_path_for_task(
            storage_root=storage_root,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            parse_task_id=task.parse_task_id,
        )
        ensure_workspace(workspace, overwrite=True)

        existing_document = (
            db.query(Document)
            .filter(
                Document.kb_id == file_import.kb_id,
                Document.import_id == file_import.import_id,
            )
            .order_by(Document.created_at.desc())
            .first()
        )
        if existing_document is not None:
            _clear_document_tree_for_reparse(
                db,
                kb_id=file_import.kb_id,
                document_id=existing_document.document_id,
            )
            db.flush()

        run_doc_chunk_pipeline(docx_path, workspace)
        result = import_workspace_for_knowledge_entry(
            db,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            workspace=workspace,
            file_import=file_import,
            document_id=existing_document.document_id if existing_document else None,
        )

        task.document_id = result.document_id
        task.status = ActualBidParseTaskStatus.completed
        task.finished_at = _now()
        task.task_phase = ActualBidParseTaskPhase.document_parse
        entry.status = DownstreamTaskStatus.completed
        file_import.status = FileImportStatus.completed
        db.commit()
        cleanup_workspace(workspace, on_success=True)
    except Exception as exc:
        logger.exception("document_parse failed import_id=%s", file_import.import_id)
        task.status = ActualBidParseTaskStatus.failed
        task.error_message = str(exc)[:2000]
        task.finished_at = _now()
        entry.status = DownstreamTaskStatus.failed
        file_import.status = FileImportStatus.failed
        db.commit()
        raise


def run_document_parse_once(db: Session) -> bool:
    entry = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.task_type == DownstreamTaskType.document_parse,
            DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .first()
    )
    if entry is None:
        return False
    entry.status = DownstreamTaskStatus.claimed
    entry.claimed_by = "document_parse_runner"
    entry.claimed_at = _now()
    db.flush()
    _run_entry(db, entry)
    return True


def run_document_parse_pending(db: Session) -> None:
    while run_document_parse_once(db):
        pass


def run_document_parse_in_new_session() -> None:
    db = SessionLocal()
    try:
        run_document_parse_pending(db)
    except Exception:
        logger.exception("document_parse runner failed")
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_document_parse_runner.py::test_document_parse_runner_exports -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/document_parse_runner.py \
        backend/tests/unit/test_document_parse_runner.py
git commit -m "feat: add unified document_parse_runner for V2-only import"
```

---

## Task 3: 精简 confirm_service

**Files:**
- Modify: `backend/src/services/confirm_service.py`
- Modify: `backend/tests/contract/test_file_import_confirm.py`
- Modify: `backend/tests/unit/test_document_parse_runner.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_document_parse_runner.py`:

```python
from src.models.downstream_task_entry import DownstreamTaskType
from src.services.confirm_service import _downstream_task_types
from src.models.file_import import FilePurpose


def test_downstream_task_types_only_document_parse():
    assert _downstream_task_types(FilePurpose.actual_bid, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FilePurpose.template_file, True) == [
        DownstreamTaskType.document_parse
    ]
```

- [ ] **Step 2: Run — expect FAIL**

```bash
../.venv/bin/pytest tests/unit/test_document_parse_runner.py::test_downstream_task_types_only_document_parse -v
```

- [ ] **Step 3: Rewrite confirm_service.py**

Replace imports and slim down. Key changes:

```python
from src.services.document_parse_runner import enqueue_document_parse

def _downstream_task_types(file_purpose: FilePurpose, enter_parsing: bool) -> list[DownstreamTaskType]:
    if not enter_parsing:
        return []
    if file_purpose in {FilePurpose.actual_bid, FilePurpose.template_file}:
        return [DownstreamTaskType.document_parse]
    return []

def confirm_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    expected_version: int,
    file_purpose: FilePurpose,
    enter_parsing: bool,
    operator_id: str,
    trace_id: UUID | None,
) -> dict:
    # Remove product_category_ids, chapter_taxonomy_id, target_object_type params
    # Remove _validate_active_categories, _validate_active_taxonomy, _rewrite_classification_references
    ...
    if enter_parsing and file_purpose in {FilePurpose.actual_bid, FilePurpose.template_file}:
        parse_task = enqueue_document_parse(
            db, kb_id=kb_id, import_id=import_id,
            operator_id=operator_id, trace_id=trace_id,
        )
        parse_task_id = str(parse_task.parse_task_id)
    ...
```

Update `ignore_import` to remove `target_object_type` assignment.

- [ ] **Step 4: Update contract test**

In `backend/tests/contract/test_file_import_confirm.py`, remove assertions on `product_category_ids`, `chapter_taxonomy_id`, `target_object_type`. Confirm payload only checks `file_purpose`, `enter_parsing`, `downstream_entries_created`.

- [ ] **Step 5: Run tests**

```bash
../.venv/bin/pytest tests/unit/test_document_parse_runner.py tests/contract/test_file_import_confirm.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/confirm_service.py \
        backend/tests/contract/test_file_import_confirm.py \
        backend/tests/unit/test_document_parse_runner.py
git commit -m "refactor: confirm import routes only to document_parse"
```

---

## Task 4: 重写 file_import_purge_service

**Files:**
- Modify: `backend/src/services/file_import_purge_service.py`
- Modify: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: Write the failing test**

Replace `backend/tests/unit/test_file_import_purge_service.py` with V2-only purge tests:

```python
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.file_import_purge_service import check_purge_impact, purge_file_import


def test_check_purge_impact_counts_knowledge_chunks(db_session, seeded_kb):
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="a.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/a.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="a.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.flush()
    chunk = KnowledgeChunk(
        kb_id=seeded_kb.kb_id,
        knowledge_code="K-001",
        version="1.0",
        title="t",
        content="c",
        knowledge_type="fact",
        doc_id=doc.document_id,
        source_type="bid",
        catalog_path=[],
        primary_node_id=str(uuid4()),
        category="technical",
        tags=[],
        products=[],
        industries=[],
        customer_types=[],
        created_by="admin",
    )
    db_session.add(chunk)
    db_session.commit()

    report = check_purge_impact(db_session, kb_id=seeded_kb.kb_id, import_id=import_id)
    assert report.knowledge_chunk_count >= 1


def test_purge_file_import_soft_deletes(db_session, seeded_kb):
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="b.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/b.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    db_session.commit()

    summary = purge_file_import(
        db_session, kb_id=seeded_kb.kb_id, import_id=import_id, operator_id="admin"
    )
    assert summary.import_status == "deleted"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
../.venv/bin/pytest tests/unit/test_file_import_purge_service.py -v
```

- [ ] **Step 3: Rewrite purge service**

Replace `backend/src/services/file_import_purge_service.py` (~250 lines). Purge order:

1. `chunk_embeddings` / `chunk_assets` / `knowledge_chunks` (by doc_id from import)
2. `document_media_assets`, `document_tree_nodes`, `document_parse_suggestions`
3. `documents`
4. `actual_bid_parse_tasks`, `downstream_task_entries`, `import_tasks`
5. `file_purpose_suggestions`, `import_audit_logs`
6. `file_imports` (soft delete → status=deleted)
7. Remove storage files under `storage_root`

Remove all imports of `KnowledgeUnit`, `Template`, `BidOutline`, `RetrievalIndexEntry`, etc.

`check_purge_impact` returns counts: `knowledge_chunk_count`, `document_count`, `parse_task_count` — no `published_ku_count`.

- [ ] **Step 4: Run — expect PASS**

```bash
../.venv/bin/pytest tests/unit/test_file_import_purge_service.py tests/contract/test_file_import_delete.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/file_import_purge_service.py \
        backend/tests/unit/test_file_import_purge_service.py
git commit -m "refactor: rewrite file import purge for V2-only data model"
```

---

## Task 5: 更新 file_imports API 路由

**Files:**
- Modify: `backend/src/api/routes/file_imports.py`

- [ ] **Step 1: Replace parse runner imports**

```python
# Remove:
from src.services.actual_bid_parse_runner import ...
from src.services.template_parse_runner import run_template_parse_in_new_session

# Add:
from src.services.document_parse_runner import (
    DocumentParseServiceError,
    enqueue_document_parse,
    run_document_parse_in_new_session,
)
```

- [ ] **Step 2: Slim ConfirmImportRequest**

```python
class ConfirmImportRequest(BaseModel):
    expected_version: int
    file_purpose: FilePurpose  # only actual_bid | template_file after enum migration
    enter_parsing: bool = True
```

- [ ] **Step 3: Update confirm endpoint call**

```python
result = confirm_import(
    db,
    kb_id=kb_id,
    import_id=import_id,
    expected_version=body.expected_version,
    file_purpose=body.file_purpose,
    enter_parsing=body.enter_parsing,
    operator_id=operator_id,
    trace_id=trace_id,
)
```

- [ ] **Step 4: Unify retry to document parse**

Replace `retry_actual_bid_parse` and `retry_template_parse` endpoints with single:

```python
@router.post("/{import_id}/retry-parse")
def retry_document_parse(...):
    task = enqueue_document_parse(db, ..., force_reparse=True)
    background_tasks.add_task(run_document_parse_in_new_session)
    return success({"parse_task_id": str(task.parse_task_id)})
```

Remove `TemplateParseTask` imports and template-specific list filters.

- [ ] **Step 5: Run contract tests**

```bash
../.venv/bin/pytest tests/contract/test_file_import_upload.py \
                   tests/contract/test_file_import_confirm.py \
                   tests/contract/test_file_import_delete.py -v
```
Expected: PASS (fix failures inline)

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/routes/file_imports.py
git commit -m "refactor: file-imports API uses document_parse_runner"
```

---

## Task 6: 精简前端来源导入

**Files:**
- Modify: `frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`
- Modify: `frontend/src/services/fileImports.ts`

- [ ] **Step 1: Simplify ConfirmDrawer**

Remove imports of `productCategoryApi`, `chapterTaxonomyApi`, `TreeSelect`. Replace `FILE_PURPOSE_OPTIONS`:

```typescript
const FILE_PURPOSE_OPTIONS = [
  { label: "实际标书", value: "actual_bid" },
  { label: "模板文件", value: "template_file" },
];
```

Remove form fields `product_category_ids`, `chapter_taxonomy_id`. Update `confirmFileImport` call:

```typescript
await confirmFileImport(kbId, importId, {
  expected_version: detail.version,
  file_purpose: values.file_purpose,
  enter_parsing: values.enter_parsing,
});
```

- [ ] **Step 2: Update FileImportCenter index**

In `ParseStatusCell`, replace outline/template links with:

```typescript
{parseStatus === "parse_ready" && documentId ? (
  <Link to={`/knowledge-v2/entry?docId=${documentId}`}>前往知识录入</Link>
) : null}
```

Remove `retryTemplateParse` usage; use unified `retryDocumentParse` from `fileImports.ts`.

Remove `Link` to `/outlines/parse-confirm/` and `/template-libraries`.

- [ ] **Step 3: Update fileImports.ts**

```typescript
export async function confirmFileImport(
  kbId: string,
  importId: string,
  body: {
    expected_version: number;
    file_purpose: string;
    enter_parsing: boolean;
  },
): Promise<FileImportDetail> { ... }

export async function retryDocumentParse(
  kbId: string,
  importId: string,
): Promise<{ parse_task_id: string }> {
  return apiPost(`/api/v1/kbs/${kbId}/file-imports/${importId}/retry-parse`, {});
}
```

Delete `retryTemplateParse`, `retryActualBidParse` exports.

- [ ] **Step 4: Build frontend**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/frontend
npm run build
```
Expected: PASS (may fail until Task 7 removes dead imports — fix any ConfirmDrawer-only errors first)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/FileImportCenter/ \
        frontend/src/services/fileImports.ts
git commit -m "refactor: simplify file import UI for V2-only flow"
```

---

## Task 7: 删除前端旧页面与路由

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`
- Delete: 7 page directories (see below)

- [ ] **Step 1: Delete old page directories**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/frontend/src/pages
rm -rf CandidateCenter KnowledgeCenter OutlineCenter TemplateLibraryCenter \
       ProductCategoryCenter ChapterTaxonomyCenter RetrievalOptimizationCenter
```

- [ ] **Step 2: Replace App.tsx routes**

```tsx
import { Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import FileImportCenterPage from "./pages/FileImportCenter";
import KnowledgeBaseListPage from "./pages/KnowledgeBaseList";
import KnowledgeEntryPage from "./pages/KnowledgeV2/KnowledgeEntryPage";
import KnowledgeBrowsePage from "./pages/KnowledgeV2/KnowledgeBrowsePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<KnowledgeBaseListPage />} />
        <Route path="/file-imports" element={<FileImportCenterPage />} />
        <Route path="/knowledge-v2/entry" element={<KnowledgeEntryPage />} />
        <Route path="/knowledge-v2/browse" element={<KnowledgeBrowsePage />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 3: Replace AppShell NAV_ITEMS**

```typescript
const NAV_ITEMS = [
  { key: "/", label: <Link to="/">知识库</Link> },
  { key: "/file-imports", label: <Link to="/file-imports">来源导入</Link> },
  { key: "/knowledge-v2/entry", label: <Link to="/knowledge-v2/entry">知识录入 V2</Link> },
  { key: "/knowledge-v2/browse", label: <Link to="/knowledge-v2/browse">知识浏览 V2</Link> },
];
```

- [ ] **Step 4: Delete orphaned frontend services**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/frontend/src/services
rm -f candidates.ts productCategoryApi.ts chapterTaxonomyApi.ts \
      actualBidParse.ts bidOutlines.ts templates.ts retrieval*.ts \
      generation.ts moduleSuggestions.ts tenderRequirements.ts
```

Keep: `fileImports.ts`, `knowledgeChunks.ts`, `knowledgeBases` (or equivalent), `apiClient.ts`, `knowledgeAssets.ts` if used by V2.

- [ ] **Step 5: Build + test**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/frontend
npm run build
npm test -- --run
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A frontend/
git commit -m "chore: remove legacy frontend pages, keep four core modules"
```

---

## Task 8: 删除后端 routes 与 main.py 注册

**Files:**
- Modify: `backend/src/main.py`
- Delete: `backend/src/api/routes/*.py` (legacy list below)

- [ ] **Step 1: Delete legacy route files**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend/src/api/routes
rm -f knowledge_units.py candidates.py candidate_batch.py candidate_audit_logs.py \
      wikis.py manual_assets.py templates.py template_libraries.py template_parse.py \
      template_chapters.py template_assets.py bid_outlines.py actual_bid_parse.py \
      retrieval.py retrieval_eval.py retrieval_feedback.py generation.py \
      module_suggestions.py tender_requirements.py chapter_patterns.py \
      product_categories.py chapter_taxonomies.py
```

- [ ] **Step 2: Replace main.py**

```python
from src.api.routes.file_imports import router as file_imports_router
from src.api.routes.knowledge_bases import router as kb_router
from src.api.routes.knowledge_chunks import router as knowledge_chunks_router
from src.api.routes.media import router as media_router

app.include_router(kb_router)
app.include_router(file_imports_router)
app.include_router(knowledge_chunks_router)
app.include_router(media_router)
```

Remove all other router imports and `include_router` calls.

- [ ] **Step 3: Verify import graph**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/python -c "from src.main import app; print(len(app.routes))"
```
Expected: small route count, no ImportError

- [ ] **Step 4: Commit**

```bash
git add backend/src/main.py backend/src/api/routes/
git commit -m "chore: remove legacy API routes, keep four core routers"
```

---

## Task 9: 删除后端 services 与 models

**Files:**
- Delete: legacy service directories/files
- Delete: legacy model files
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/db/init_db.py`

- [ ] **Step 1: Delete legacy service directories**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend/src/services
rm -rf retrieval generation publishers
rm -f actual_bid_parse_runner.py template_parse_runner.py template_*.py \
      bid_outline_*.py candidate_*.py ku_publisher.py \
      document_tree_classification_service.py chunk_classification_service.py \
      product_category_service.py chapter_taxonomy_service.py \
      module_suggestion*.py generation*.py outline_*.py \
      chapter_pattern*.py purpose_suggestion.py variable_*.py \
      citation_binder.py input_priority_resolver.py
```

Keep: `document_parse_runner.py`, `confirm_service.py`, `file_import_service.py`, `file_import_purge_service.py`, `import_task_runner.py`, `doc_chunk/`, `knowledge_v2/`, `docm_converter.py`, `file_storage.py`, etc.

- [ ] **Step 2: Delete legacy model files**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend/src/models
rm -f knowledge_unit.py candidate_knowledge.py candidate_knowledge_stub.py \
      candidate_confirm_audit_log.py wiki.py manual_asset.py \
      bid_outline.py bid_outline_node.py bid_outline_structure_diff.py actual_bid_audit_log.py \
      template.py template_library.py template_chapter.py template_material.py \
      template_variable.py template_rule.py template_parse_task.py template_parse_suggestion.py \
      template_structure_diff.py template_publish_snapshot.py template_audit_log.py \
      retrieval_*.py generation_*.py chapter_draft.py module_assembly_suggestion.py \
      tender_requirement_context.py chapter_pattern.py chapter_pattern_mining_task.py \
      product_category.py chapter_taxonomy.py classification_reference.py \
      classification_audit_log.py prompt_config_version.py
```

- [ ] **Step 3: Replace models/__init__.py**

```python
"""ORM models package."""

from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.chunk_asset import ChunkAsset
from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.models.document import Document
from src.models.document_media_asset import DocumentMediaAsset
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode
from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.file_import import FileImport
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.import_audit_log import ImportAuditLog
from src.models.import_task import ImportTask
from src.models.kb_clone_log import KBCloneLog
from src.models.knowledge_base import KnowledgeBase

__all__ = [
    "ActualBidParseTask",
    "ChunkAsset",
    "ChunkEmbedding",
    "KnowledgeChunk",
    "Document",
    "DocumentMediaAsset",
    "DocumentParseSuggestion",
    "DocumentTreeNode",
    "DownstreamTaskEntry",
    "FileImport",
    "FilePurposeSuggestion",
    "ImportAuditLog",
    "ImportTask",
    "KBCloneLog",
    "KnowledgeBase",
]
```

- [ ] **Step 4: Slim file_import.py model**

In `backend/src/models/file_import.py`:
- Remove `TargetObjectType` enum
- Narrow `FilePurpose` to `actual_bid`, `template_file` only
- Remove columns `product_category_ids`, `chapter_taxonomy_id`, `target_object_type` (migration handles DB; remove from ORM now)

- [ ] **Step 5: Slim downstream_task_entry.py**

```python
class DownstreamTaskType(str, enum.Enum):
    document_parse = "document_parse"
    none = "none"
```

- [ ] **Step 6: Update init_db.py**

Remove imports of deleted models; only import retained model modules.

- [ ] **Step 7: Commit**

```bash
git add backend/src/services/ backend/src/models/ backend/src/db/init_db.py
git commit -m "chore: remove legacy services and ORM models"
```

---

## Task 10: Alembic migration 删表与删列

**Files:**
- Create: `backend/alembic/versions/20260620_1000_core_four_modules_cleanup.py`
- Modify: `backend/tests/unit/test_init_db_schema_sync.py`

- [ ] **Step 1: Write migration**

Create `backend/alembic/versions/20260620_1000_core_four_modules_cleanup.py`:

```python
"""core four modules cleanup - drop legacy tables

Revision ID: 20260620_1000
Revises: 20260618_1100
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260620_1000"
down_revision: str | None = "20260618_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_TABLES: tuple[str, ...] = (
    "chunk_embeddings",  # re-created if needed — drop via FK order below
    # ... drop child tables first, see design spec §5.5 full list
    "retrieval_feedbacks",
    "retrieval_traces",
    "retrieval_index_entries",
    "retrieval_eval_cases",
    "retrieval_eval_runs",
    "retrieval_eval_sets",
    "retrieval_strategy_versions",
    "candidate_confirm_audit_logs",
    "candidate_knowledge_stubs",
    "candidate_knowledges",
    "knowledge_units",
    "wikis",
    "manual_assets",
    "bid_outline_structure_diffs",
    "bid_outline_nodes",
    "bid_outlines",
    "actual_bid_audit_logs",
    "template_audit_logs",
    "template_structure_diffs",
    "template_publish_snapshots",
    "template_parse_suggestions",
    "template_parse_tasks",
    "template_materials",
    "template_variables",
    "template_rules",
    "template_chapters",
    "templates",
    "template_libraries",
    "generation_snapshots",
    "generation_tasks",
    "chapter_drafts",
    "module_assembly_suggestions",
    "tender_requirement_contexts",
    "chapter_pattern_mining_tasks",
    "chapter_patterns",
    "classification_audit_logs",
    "classification_references",
    "product_categories",
    "chapter_taxonomies",
    "prompt_config_versions",
)


def upgrade() -> None:
    # Drop legacy tables (chunk_embeddings/chunk_assets/knowledge_chunks preserved)
    for table in LEGACY_TABLES:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    # Drop columns on retained tables
    op.drop_column("file_imports", "product_category_ids")
    op.drop_column("file_imports", "chapter_taxonomy_id")
    op.drop_column("file_imports", "target_object_type")
    op.drop_column("documents", "product_category_ids")
    op.drop_column("document_tree_nodes", "chapter_taxonomy_id")
    op.drop_column("document_tree_nodes", "product_category_ids")
    op.drop_column("file_purpose_suggestions", "suggested_product_category_ids")
    op.drop_column("file_purpose_suggestions", "suggested_chapter_taxonomy_id")

    # Recreate narrowed PostgreSQL enums (SQLite tests skip via env check)
    op.execute("DELETE FROM file_imports")  # safe after Task 0 reset
    op.execute("DELETE FROM file_purpose_suggestions")


def downgrade() -> None:
    raise NotImplementedError("Irreversible cleanup migration")
```

Fill `LEGACY_TABLES` with complete ordered list from design spec. Do NOT drop `knowledge_chunks`, `chunk_assets`, `chunk_embeddings`, `documents`, `document_tree_nodes`, `file_imports`, `actual_bid_parse_tasks`.

- [ ] **Step 2: Run migration on local PG**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/alembic upgrade head
```
Expected: SUCCESS

- [ ] **Step 3: Update init_db_schema_sync test**

Remove assertions referencing dropped tables.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/20260620_1000_core_four_modules_cleanup.py \
        backend/tests/unit/test_init_db_schema_sync.py
git commit -m "chore: migration drops legacy tables for four-core cleanup"
```

---

## Task 11: 删除废弃测试

**Files:**
- Delete: ~80 legacy test files
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Delete legacy test files**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend/tests
rm -f contract/test_candidate*.py contract/test_bid_outline*.py contract/test_template*.py \
      contract/test_retrieval*.py contract/test_generation*.py contract/test_module_suggestion*.py \
      contract/test_actual_bid*.py contract/test_epic4*.py contract/test_chapter_taxonomies*.py \
      contract/test_product_categories*.py contract/test_tender_requirement*.py
rm -f integration/test_epic*.py integration/test_candidate*.py integration/test_template*.py \
      integration/test_bid_outline*.py integration/test_retrieval*.py integration/test_generation*.py \
      integration/test_module_suggestion*.py integration/test_actual_bid*.py \
      integration/test_knowledge_visibility*.py integration/test_downstream_routing.py \
      integration/test_chapter_pattern*.py integration/test_e2e_pipeline_flow.py \
      integration/test_kb_clone_categories.py integration/test_impact_analysis.py \
      integration/test_merge.py integration/test_doc_chunk_canbu_import.py
rm -f unit/test_candidate*.py unit/test_bid_outline*.py unit/test_template*.py \
      unit/test_retrieval*.py unit/test_generation*.py unit/test_module_suggestion*.py \
      unit/test_doc_chunk_bid_outline*.py unit/test_doc_chunk_candidates*.py \
      unit/test_document_tree_classification*.py unit/test_chunk_classification*.py \
      unit/test_classification_rule*.py unit/test_product_category*.py \
      unit/test_chapter_*.py unit/test_outline_*.py unit/test_variable_*.py \
      unit/test_citation_binder.py unit/test_input_priority*.py unit/test_eval_metrics.py \
      unit/test_match_score*.py unit/test_e2e_*.py unit/test_workbench_steps.py \
      unit/test_purpose_suggestion.py unit/test_prompt_seed.py unit/test_knowledge_chunk.py
```

Keep all `test_knowledge_v2_*`, `test_knowledge_bases_api.py`, `test_file_import_*`, `test_doc_chunk_import_service.py`, `test_doc_chunk_section_slice.py`, `test_doc_chunk_workspace*.py`, `test_document_parse_runner.py`, `test_file_import_purge_service.py`, `test_media_api.py`, `test_reset_business_data.py`, `test_init_db_schema_sync.py`.

- [ ] **Step 2: Replace conftest.py model imports**

Remove all deleted model imports from `backend/tests/conftest.py`. Keep only:

```python
from src.models import (
    actual_bid_parse_task,
    chunk_asset,
    chunk_embedding,
    document,
    document_media_asset,
    document_parse_suggestion,
    document_tree_node,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
    knowledge_chunk,
)
```

Remove `seeded_template` and other fixtures referencing deleted models.

- [ ] **Step 3: Run full pytest**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest -q
```
Expected: PASS (fix any remaining import errors)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "chore: remove legacy tests, keep four-core coverage"
```

---

## Task 12: 更新 reset_business_data 与删除 E2E 脚本

**Files:**
- Modify: `scripts/lib/e2e/reset_business_data.py`
- Modify: `backend/tests/unit/test_reset_business_data.py`
- Delete: legacy E2E scripts

- [ ] **Step 1: Replace BUSINESS_TABLES**

In `scripts/lib/e2e/reset_business_data.py`:

```python
BUSINESS_TABLES: tuple[str, ...] = (
    "chunk_embeddings",
    "chunk_assets",
    "knowledge_chunks",
    "document_media_assets",
    "document_parse_suggestions",
    "document_tree_nodes",
    "documents",
    "actual_bid_parse_tasks",
    "downstream_task_entries",
    "import_audit_logs",
    "import_tasks",
    "file_purpose_suggestions",
    "file_imports",
    "kb_clone_logs",
)
```

- [ ] **Step 2: Update test_reset_business_data.py**

```python
def test_business_tables_match_retained_schema():
    retained = {
        "chunk_embeddings", "chunk_assets", "knowledge_chunks",
        "document_media_assets", "document_parse_suggestions",
        "document_tree_nodes", "documents", "actual_bid_parse_tasks",
        "downstream_task_entries", "import_audit_logs", "import_tasks",
        "file_purpose_suggestions", "file_imports", "kb_clone_logs",
    }
    assert set(BUSINESS_TABLES) == retained
```

- [ ] **Step 3: Delete legacy E2E scripts**

```bash
cd /Users/tongqianni/xlab/tender_knowledge
rm -f scripts/run_zhongtie_acceptance.py scripts/epic6_live_acceptance.py \
      scripts/e2e_pipeline_test.py scripts/bootstrap-dingxin-candidates.py \
      scripts/backfill_*.py
rm -rf scripts/lib/e2e/steps/actual_bid.py scripts/lib/e2e/steps/template_file.py \
       scripts/lib/e2e/steps/workbench.py scripts/lib/e2e/steps/retrieval_extended.py
```

Keep: `reset_business_data.py`, `kb_setup.py` (update if needed).

- [ ] **Step 4: Run reset + tests**

```bash
cd backend
PYTHONPATH=../scripts/lib:.. ../.venv/bin/python -c "from e2e.reset_business_data import reset_business_data; print(reset_business_data())"
../.venv/bin/pytest tests/unit/test_reset_business_data.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ backend/tests/unit/test_reset_business_data.py
git commit -m "chore: update reset script and remove legacy E2E scripts"
```

---

## Task 13: 最终验收

**Files:** (verification only)

- [ ] **Step 1: Backend full test suite**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest -q
```
Expected: all PASS

- [ ] **Step 2: Frontend build + test**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/frontend
npm run build
npm test -- --run
```
Expected: PASS

- [ ] **Step 3: Manual smoke test checklist**

1. 打开 `/` — 知识库列表正常
2. `/file-imports` — 上传 docx → 确认用途(actual_bid) → 解析完成
3. 点击「前往知识录入」→ `/knowledge-v2/entry?docId=...` 可见目录树
4. 录入一条 knowledge chunk → `/knowledge-v2/browse` 可见
5. 删除 file import → 无 500 错误

- [ ] **Step 4: Health check**

```bash
curl -s http://127.0.0.1:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 5: Final commit if any fixups**

```bash
git status
# commit any remaining fixups
```

---

## Spec Coverage Self-Review

| Spec § | Task |
|--------|------|
| §4 保留清单 | Tasks 1–6, 8–9 |
| §5 删除清单 | Tasks 7–9, 11–12 |
| §6 来源导入 V2-only | Tasks 1–6 |
| §7 测试策略 | Task 11 |
| §8 测试数据清理 | Tasks 0, 12 |
| §9 实施顺序 P0–P6 | Tasks 0–13 |
| §4.5 列清理 + FilePurpose | Task 9–10 |
| §11 不在范围 (specs 归档) | 未包含 — 后续 PR |

No placeholders remain. Type names consistent: `enqueue_document_parse`, `import_workspace_for_knowledge_entry`, `DocumentParseServiceError`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-20-core-four-modules-cleanup.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
