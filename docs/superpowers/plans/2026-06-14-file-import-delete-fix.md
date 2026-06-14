# 来源导入删除 500 修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复来源导入 DELETE 500，引入已发布资产保护（409 + 级联废弃确认），以墓碑状态软删除 import 记录。

**Architecture:** 扩展 `FileImportStatus.deleted`；重构 `file_import_purge_service` 为 impact 预览 / 废弃 / 软清理三阶段；DELETE 增加 `deprecate_published` 查询参数；前端 FileImportCenter 按影响分岔确认流程。废弃资产在清理 documents 前须 detach `source_doc_id` / `source_node_id` / `bid_outline_id` 以避免 FK 冲突。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pytest, httpx | TypeScript, React 18, Ant Design 5, Vite

**Design doc:** `docs/superpowers/specs/2026-06-14-file-import-delete-fix-design.md`

---

## File Map

| 路径 | 职责 | 操作 |
|------|------|------|
| `backend/src/models/file_import.py` | 新增 `FileImportStatus.deleted` | Modify |
| `backend/src/db/init_db.py` | PostgreSQL enum 同步 `fileimportstatus` | Modify |
| `backend/src/services/file_import_purge_service.py` | impact / deprecate / soft purge 重构 | Modify |
| `backend/src/api/routes/file_imports.py` | purge-impact 路由、DELETE 参数、列表过滤 | Modify |
| `backend/tests/contract/test_file_import_delete.py` | 删除契约测试 | Create |
| `backend/tests/unit/test_file_import_purge_service.py` | purge 服务单元测试 | Create |
| `frontend/src/services/fileImports.ts` | purge-impact API + delete 参数 | Modify |
| `frontend/src/pages/FileImportCenter/index.tsx` | 分岔删除 UX | Modify |
| `frontend/src/components/ImpactAnalysisModal.tsx` | 复用展示 + destroyOnHidden | Modify |
| `frontend/src/components/MergeWizard.tsx` | destroyOnHidden | Modify |
| `frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx` | destroyOnHidden | Modify |
| `frontend/src/pages/FileImportCenter/TaskLogDrawer.tsx` | destroyOnHidden | Modify |
| `frontend/src/pages/KnowledgeBaseList/index.tsx` | destroyOnHidden | Modify |
| `frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx` | destroyOnHidden | Modify |
| `frontend/src/pages/TemplateLibraryCenter/PublishModal.tsx` | destroyOnHidden | Modify |

---

## Task 1: FileImport 墓碑枚举 + PostgreSQL 同步

**Files:**
- Modify: `backend/src/models/file_import.py`
- Modify: `backend/src/db/init_db.py`
- Create: `backend/tests/unit/test_file_import_status_enum.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_file_import_status_enum.py
from src.models.file_import import FileImportStatus


def test_file_import_status_has_deleted():
    assert FileImportStatus.deleted.value == "deleted"
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_status_enum.py -v`

Expected: FAIL — `AttributeError: deleted`

- [ ] **Step 3: 新增枚举值 + init_db 同步**

```python
# backend/src/models/file_import.py — FileImportStatus 内追加
class FileImportStatus(str, enum.Enum):
    uploaded = "uploaded"
    need_confirm = "need_confirm"
    confirmed = "confirmed"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    ignored = "ignored"
    deleted = "deleted"
```

```python
# backend/src/db/init_db.py — 在 import 区追加
from src.models.file_import import FileImportStatus

# init_db() 的 with engine.begin() 块内、_sync_missing_columns 之前追加：
        _sync_postgres_enum(
            conn,
            "fileimportstatus",
            [member.value for member in FileImportStatus],
        )
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_status_enum.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/file_import.py backend/src/db/init_db.py backend/tests/unit/test_file_import_status_enum.py
git commit -m "feat: add FileImportStatus.deleted tombstone state"
```

---

## Task 2: Purge Impact 预览服务

**Files:**
- Modify: `backend/src/services/file_import_purge_service.py`
- Create: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: 写失败测试 — impact 计数**

```python
# backend/tests/unit/test_file_import_purge_service.py
from uuid import uuid4

from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus, CandidateKnowledgeType
from src.models.document import Document
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.services.file_import_purge_service import check_purge_impact


def _seed_import(db_session, kb_id):
    imp = FileImport(
        kb_id=kb_id,
        file_name="test.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="/tmp/test.docx",
        status=FileImportStatus.completed,
        file_purpose=FilePurpose.actual_bid,
        created_by="tester",
    )
    db_session.add(imp)
    db_session.flush()
    return imp


def test_check_purge_impact_counts_published_ku(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        file_name="test.docx",
        file_type="docx",
        storage_path="/tmp/test.docx",
    )
    db_session.add(doc)
    db_session.flush()
    db_session.add(
        KnowledgeUnit(
            kb_id=seeded_kb.kb_id,
            title="KU",
            content="body",
            knowledge_type="solution",
            product_category_ids=[],
            import_id=imp.import_id,
            candidate_id=uuid4(),
            published_by="tester",
            status=KnowledgeUnitStatus.published,
            source_doc_id=doc.document_id,
        )
    )
    db_session.add(
        CandidateKnowledge(
            kb_id=seeded_kb.kb_id,
            import_id=imp.import_id,
            document_id=doc.document_id,
            node_id=uuid4(),
            title="cand",
            content="c",
            knowledge_type=CandidateKnowledgeType.solution,
            status=CandidateKnowledgeStatus.pending,
        )
    )
    db_session.commit()

    report = check_purge_impact(db_session, kb_id=seeded_kb.kb_id, import_id=imp.import_id)
    assert report.has_published_assets is True
    assert report.published_counts["ku"] == 1
    assert report.published_total == 1
    assert report.intermediate_counts["candidate_knowledges"] == 1
    assert report.intermediate_counts["documents"] == 1
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py::test_check_purge_impact_counts_published_ku -v`

Expected: FAIL — `ImportError: cannot import name 'check_purge_impact'`

- [ ] **Step 3: 实现 `PurgeImpactReport` 与 `check_purge_impact`**

```python
# backend/src/services/file_import_purge_service.py — 在 PurgeSummary 后追加

@dataclass
class PurgeImpactReport:
    import_id: str
    file_name: str
    has_published_assets: bool
    published_counts: dict[str, int]
    published_total: int
    intermediate_counts: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "import_id": self.import_id,
            "file_name": self.file_name,
            "has_published_assets": self.has_published_assets,
            "published_counts": self.published_counts,
            "published_total": self.published_total,
            "intermediate_counts": self.intermediate_counts,
        }


def check_purge_impact(db: Session, *, kb_id: UUID, import_id: UUID) -> PurgeImpactReport:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status == FileImportStatus.deleted:
        return PurgeImpactReport(
            import_id=str(import_id),
            file_name=record.file_name,
            has_published_assets=False,
            published_counts={},
            published_total=0,
            intermediate_counts={},
        )

    published_counts = {
        "ku": db.query(KnowledgeUnit)
        .filter(
            KnowledgeUnit.kb_id == kb_id,
            KnowledgeUnit.import_id == import_id,
            KnowledgeUnit.status == KnowledgeUnitStatus.published,
        )
        .count(),
        "wiki": db.query(Wiki)
        .filter(
            Wiki.kb_id == kb_id,
            Wiki.import_id == import_id,
            Wiki.status == WikiStatus.published,
        )
        .count(),
        "manual_asset": db.query(ManualAsset)
        .filter(
            ManualAsset.kb_id == kb_id,
            ManualAsset.import_id == import_id,
            ManualAsset.status == ManualAssetStatus.published,
        )
        .count(),
    }
    published_total = sum(published_counts.values())
    intermediate_counts = {
        "candidate_knowledges": db.query(CandidateKnowledge)
        .filter(CandidateKnowledge.import_id == import_id)
        .count(),
        "documents": db.query(Document).filter(Document.import_id == import_id).count(),
        "import_tasks": db.query(ImportTask).filter(ImportTask.import_id == import_id).count(),
    }
    return PurgeImpactReport(
        import_id=str(import_id),
        file_name=record.file_name,
        has_published_assets=published_total > 0,
        published_counts={k: v for k, v in published_counts.items() if v > 0},
        published_total=published_total,
        intermediate_counts={k: v for k, v in intermediate_counts.items() if v > 0},
    )
```

在文件顶部 import 区追加：

```python
from datetime import datetime, timezone
from src.models.document_media_asset import DocumentMediaAsset
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.models.manual_asset import ManualAsset, ManualAssetStatus
from src.models.wiki import Wiki, WikiStatus
from src.models.file_import import FileImportStatus
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalObjectType
from src.services.retrieval.indexing.index_builder import IndexBuilder
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py::test_check_purge_impact_counts_published_ku -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/file_import_purge_service.py backend/tests/unit/test_file_import_purge_service.py
git commit -m "feat: add file import purge impact preview"
```

---

## Task 3: 级联废弃 + 软清理核心逻辑

**Files:**
- Modify: `backend/src/services/file_import_purge_service.py`
- Modify: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: 写失败测试 — 无已发布资产软删除**

```python
# 追加到 backend/tests/unit/test_file_import_purge_service.py
from src.models.file_import import FileImportStatus
from src.services.file_import_purge_service import purge_file_import


def test_purge_without_published_soft_deletes_import(db_session, seeded_kb, monkeypatch):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        file_name="test.docx",
        file_type="docx",
        storage_path="/tmp/test.docx",
    )
    db_session.add(doc)
    db_session.commit()

    summary = purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        operator_id="tester",
        trace_id=None,
        deprecate_published=False,
    )
    db_session.commit()

    refreshed = db_session.get(FileImport, imp.import_id)
    assert refreshed is not None
    assert refreshed.status == FileImportStatus.deleted
    assert summary.deleted_counts.get("documents") == 1
    assert db_session.query(Document).filter(Document.import_id == imp.import_id).count() == 0
```

- [ ] **Step 2: 写失败测试 — 有已发布 KU 拒绝删除**

```python
def test_purge_with_published_ku_raises_without_flag(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.add(
        KnowledgeUnit(
            kb_id=seeded_kb.kb_id,
            title="KU",
            content="body",
            knowledge_type="solution",
            product_category_ids=[],
            import_id=imp.import_id,
            candidate_id=uuid4(),
            published_by="tester",
            status=KnowledgeUnitStatus.published,
        )
    )
    db_session.commit()

    import pytest
    from src.services.file_import_purge_service import FileImportPurgeServiceError

    with pytest.raises(FileImportPurgeServiceError) as exc:
        purge_file_import(
            db_session,
            kb_id=seeded_kb.kb_id,
            import_id=imp.import_id,
            operator_id="tester",
            trace_id=None,
            deprecate_published=False,
        )
    assert exc.value.code == "PUBLISHED_ASSETS_EXIST"
    assert exc.value.status_code == 409
```

- [ ] **Step 3: 写失败测试 — 确认后级联废弃**

```python
def test_purge_with_published_ku_deprecates_when_confirmed(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    ku = KnowledgeUnit(
        kb_id=seeded_kb.kb_id,
        title="KU",
        content="body",
        knowledge_type="solution",
        product_category_ids=[],
        import_id=imp.import_id,
        candidate_id=uuid4(),
        published_by="tester",
        status=KnowledgeUnitStatus.published,
    )
    db_session.add(ku)
    db_session.commit()

    summary = purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        operator_id="tester",
        trace_id=None,
        deprecate_published=True,
    )
    db_session.commit()
    db_session.refresh(ku)

    assert ku.status == KnowledgeUnitStatus.deprecated
    assert ku.deprecated_at is not None
    assert summary.deprecated_counts.get("ku") == 1
    assert db_session.get(FileImport, imp.import_id).status == FileImportStatus.deleted
```

- [ ] **Step 4: 运行测试确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py -v -k "purge"`

Expected: FAIL — 参数或逻辑未实现

- [ ] **Step 5: 实现废弃、detach、软清理**

扩展 `PurgeSummary`：

```python
@dataclass
class PurgeSummary:
    import_id: str
    file_name: str
    status: str = "deleted"
    deleted_counts: dict[str, int] = field(default_factory=dict)
    deprecated_counts: dict[str, int] = field(default_factory=dict)
```

新增 helper：

```python
def _deprecate_published_assets(db: Session, *, kb_id: UUID, import_id: UUID) -> dict[str, int]:
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    index_builder = IndexBuilder(db)

    kus = (
        db.query(KnowledgeUnit)
        .filter(
            KnowledgeUnit.kb_id == kb_id,
            KnowledgeUnit.import_id == import_id,
            KnowledgeUnit.status == KnowledgeUnitStatus.published,
        )
        .all()
    )
    for ku in kus:
        ku.status = KnowledgeUnitStatus.deprecated
        ku.deprecated_at = now
        index_builder.deprecate_entry(
            kb_id=kb_id, object_type=RetrievalObjectType.ku, object_id=ku.ku_id
        )
    if kus:
        _inc(counts, "ku", len(kus))

    wikis = (
        db.query(Wiki)
        .filter(
            Wiki.kb_id == kb_id,
            Wiki.import_id == import_id,
            Wiki.status == WikiStatus.published,
        )
        .all()
    )
    for wiki in wikis:
        wiki.status = WikiStatus.deprecated
        wiki.deprecated_at = now
        index_builder.deprecate_entry(
            kb_id=kb_id, object_type=RetrievalObjectType.wiki, object_id=wiki.wiki_id
        )
    if wikis:
        _inc(counts, "wiki", len(wikis))

    assets = (
        db.query(ManualAsset)
        .filter(
            ManualAsset.kb_id == kb_id,
            ManualAsset.import_id == import_id,
            ManualAsset.status == ManualAssetStatus.published,
        )
        .all()
    )
    for asset in assets:
        asset.status = ManualAssetStatus.deprecated
        asset.deprecated_at = now
        index_builder.deprecate_entry(
            kb_id=kb_id,
            object_type=RetrievalObjectType.manual_asset,
            object_id=asset.manual_asset_id,
        )
    if assets:
        _inc(counts, "manual_asset", len(assets))

    db.flush()
    return counts


def _detach_deprecated_asset_sources(db: Session, *, kb_id: UUID, import_id: UUID) -> None:
    """废弃资产仍引用 documents/outlines，清理中间数据前须解除 FK。"""
    for model in (KnowledgeUnit, Wiki, ManualAsset):
        db.query(model).filter(
            model.kb_id == kb_id,
            model.import_id == import_id,
        ).update(
            {
                "source_doc_id": None,
                "source_node_id": None,
            },
            synchronize_session=False,
        )
    db.query(KnowledgeUnit).filter(
        KnowledgeUnit.kb_id == kb_id,
        KnowledgeUnit.import_id == import_id,
    ).update({"bid_outline_id": None}, synchronize_session=False)
    db.flush()
```

修改 `_purge_import_core` 签名与末尾逻辑：

```python
def _purge_import_core(
    db: Session,
    record: FileImport,
    counts: dict[str, int],
    *,
    deprecate_published: bool,
    deprecated_counts: dict[str, int],
) -> None:
    import_id = record.import_id
    kb_id = record.kb_id
    # ... 子 import 递归时传递 deprecate_published / deprecated_counts ...

    impact = check_purge_impact(db, kb_id=kb_id, import_id=import_id)
    if impact.has_published_assets:
        if not deprecate_published:
            raise FileImportPurgeServiceError(
                "Published knowledge assets exist; set deprecate_published=true to proceed",
                code="PUBLISHED_ASSETS_EXIST",
                status_code=409,
            )
        merged = _deprecate_published_assets(db, kb_id=kb_id, import_id=import_id)
        for key, val in merged.items():
            _inc(deprecated_counts, key, val)

    _detach_deprecated_asset_sources(db, kb_id=kb_id, import_id=import_id)

    document_ids = [
        row.document_id for row in db.query(Document).filter(Document.import_id == import_id).all()
    ]
    if document_ids:
        n = (
            db.query(DocumentMediaAsset)
            .filter(DocumentMediaAsset.document_id.in_(document_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "document_media_assets", n)

    n = (
        db.query(RetrievalIndexEntry)
        .filter(RetrievalIndexEntry.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "retrieval_index_entries", n)

    # ... 现有 candidate / actual_bid / template 清理逻辑保持不变 ...

    if _delete_storage_dir(kb_id, import_id):
        _inc(counts, "storage_dirs", 1)

    record.status = FileImportStatus.deleted
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    _inc(counts, "file_imports", 1)
```

修改 `purge_file_import`：

```python
def purge_file_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    operator_id: str,
    trace_id: UUID | None,
    deprecate_published: bool = False,
    _skip_child_check: bool = False,
) -> PurgeSummary:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status == FileImportStatus.deleted:
        return PurgeSummary(import_id=str(import_id), file_name=record.file_name)

    counts: dict[str, int] = {}
    deprecated_counts: dict[str, int] = {}
    db.add(ImportAuditLog(...))  # 保持现有 audit 逻辑
    db.flush()

    try:
        _purge_import_core(
            db,
            record,
            counts,
            deprecate_published=deprecate_published,
            deprecated_counts=deprecated_counts,
        )
    except FileImportPurgeServiceError as exc:
        if exc.code == "PUBLISHED_ASSETS_EXIST":
            exc.details = check_purge_impact(db, kb_id=kb_id, import_id=import_id).to_dict()
        raise

    db.flush()
    return PurgeSummary(
        import_id=str(import_id),
        file_name=record.file_name,
        deleted_counts=counts,
        deprecated_counts=deprecated_counts,
    )
```

在 `FileImportPurgeServiceError` 增加可选 `details` 字段：

```python
class FileImportPurgeServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int, details: dict | None = None):
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)
```

- [ ] **Step 6: 运行测试确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py -v`

Expected: PASS（全部用例）

- [ ] **Step 7: Commit**

```bash
git add backend/src/services/file_import_purge_service.py backend/tests/unit/test_file_import_purge_service.py
git commit -m "feat: soft purge imports with published asset deprecation"
```

---

## Task 4: API 路由 — purge-impact / DELETE 参数 / 列表过滤

**Files:**
- Modify: `backend/src/api/routes/file_imports.py`
- Create: `backend/tests/contract/test_file_import_delete.py`

- [ ] **Step 1: 写失败契约测试 — 无已发布资产删除成功**

```python
# backend/tests/contract/test_file_import_delete.py
from uuid import uuid4

from src.models.document import Document
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType


def _seed_import(db_session, kb_id):
    imp = FileImport(
        kb_id=kb_id,
        file_name="del-test.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="/tmp/del-test.docx",
        status=FileImportStatus.completed,
        file_purpose=FilePurpose.actual_bid,
        created_by="tester",
    )
    db_session.add(imp)
    db_session.flush()
    return imp


def test_delete_import_without_published_assets(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.add(
        Document(
            kb_id=seeded_kb.kb_id,
            import_id=imp.import_id,
            file_name="del-test.docx",
            file_type="docx",
            storage_path="/tmp/del-test.docx",
        )
    )
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "deleted"
    assert db_session.get(FileImport, imp.import_id).status == FileImportStatus.deleted

    listed = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "tester"},
    )
    ids = [item["import_id"] for item in listed.json()["data"]["items"]]
    assert str(imp.import_id) not in ids
```

- [ ] **Step 2: 写失败契约测试 — 有已发布 KU 返回 409**

```python
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus


def test_delete_import_with_published_ku_returns_409(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.add(
        KnowledgeUnit(
            kb_id=seeded_kb.kb_id,
            title="Published KU",
            content="body",
            knowledge_type="solution",
            product_category_ids=[],
            import_id=imp.import_id,
            candidate_id=uuid4(),
            published_by="tester",
            status=KnowledgeUnitStatus.published,
        )
    )
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PUBLISHED_ASSETS_EXIST"
    assert resp.json()["error"]["details"]["published_counts"]["ku"] == 1
```

- [ ] **Step 3: 写失败契约测试 — deprecate_published 成功**

```python
def test_delete_import_deprecates_published_ku(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    ku = KnowledgeUnit(
        kb_id=seeded_kb.kb_id,
        title="Published KU",
        content="body",
        knowledge_type="solution",
        product_category_ids=[],
        import_id=imp.import_id,
        candidate_id=uuid4(),
        published_by="tester",
        status=KnowledgeUnitStatus.published,
    )
    db_session.add(ku)
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}?deprecate_published=true",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    db_session.refresh(ku)
    assert ku.status == KnowledgeUnitStatus.deprecated
```

- [ ] **Step 4: 写失败契约测试 — purge-impact**

```python
def test_purge_impact_returns_counts(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}/purge-impact",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["import_id"] == str(imp.import_id)
    assert resp.json()["data"]["has_published_assets"] is False
```

- [ ] **Step 5: 运行契约测试确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_file_import_delete.py -v`

Expected: FAIL — 404 路由不存在或 500

- [ ] **Step 6: 实现 API 变更**

```python
# backend/src/api/routes/file_imports.py

from sqlalchemy.exc import IntegrityError
from src.services.file_import_purge_service import check_purge_impact

# list_file_imports — 第 78 行 filter 追加：
    q = db.query(FileImport).filter(
        FileImport.kb_id == kb_id,
        FileImport.status != FileImportStatus.deleted,
    )

# 在 delete_file_import 之前新增：
@router.get("/{import_id}/purge-impact")
def get_file_import_purge_impact(
    kb_id: UUID,
    import_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        report = check_purge_impact(db, kb_id=kb_id, import_id=import_id)
    except FileImportPurgeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(report.to_dict(), trace_id=get_trace_id())

# delete_file_import — 增加 query 参数 + IntegrityError：
@router.delete("/{import_id}")
def delete_file_import(
    kb_id: UUID,
    import_id: UUID,
    deprecate_published: bool = False,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        summary = purge_file_import(
            db,
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            deprecate_published=deprecate_published,
        )
        db.commit()
    except FileImportPurgeServiceError as exc:
        db.rollback()
        return JSONResponse(
            status_code=exc.status_code,
            content=error(
                exc.code,
                str(exc),
                trace_id=get_trace_id(),
                details=getattr(exc, "details", None),
            ),
        )
    except IntegrityError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "PURGE_CONFLICT",
                "Unable to purge import due to remaining references",
                trace_id=get_trace_id(),
            ),
        )
    return success(
        {
            "import_id": summary.import_id,
            "file_name": summary.file_name,
            "status": summary.status,
            "deprecated_counts": summary.deprecated_counts,
            "deleted_counts": summary.deleted_counts,
        },
        trace_id=get_trace_id(),
    )
```

确认 `error()` helper 支持 `details` 关键字参数；若不支持，在 `src/api/envelope.py` 的 `error()` 增加可选 `details: dict | None = None` 并写入 `error.details`。

- [ ] **Step 7: 运行契约测试确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_file_import_delete.py -v`

Expected: PASS（4 用例）

- [ ] **Step 8: Commit**

```bash
git add backend/src/api/routes/file_imports.py backend/src/api/envelope.py backend/tests/contract/test_file_import_delete.py
git commit -m "feat: file import purge-impact API and soft delete endpoint"
```

---

## Task 5: 前端 API 与删除 UX

**Files:**
- Modify: `frontend/src/services/fileImports.ts`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`
- Modify: `frontend/src/components/ImpactAnalysisModal.tsx`

- [ ] **Step 1: 扩展 fileImports 服务**

```typescript
// frontend/src/services/fileImports.ts

export interface FileImportPurgeImpact {
  import_id: string;
  file_name: string;
  has_published_assets: boolean;
  published_counts: Record<string, number>;
  published_total: number;
  intermediate_counts: Record<string, number>;
}

export async function getFileImportPurgeImpact(
  kbId: string,
  importId: string,
): Promise<FileImportPurgeImpact> {
  return apiRequest<FileImportPurgeImpact>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}/purge-impact`,
    { method: "GET" },
  );
}

export interface DeleteFileImportResult {
  import_id: string;
  file_name: string;
  status: string;
  deprecated_counts: Record<string, number>;
  deleted_counts: Record<string, number>;
}

export async function deleteFileImport(
  kbId: string,
  importId: string,
  options?: { deprecatePublished?: boolean },
): Promise<DeleteFileImportResult> {
  const params = new URLSearchParams();
  if (options?.deprecatePublished) {
    params.set("deprecate_published", "true");
  }
  const query = params.toString();
  return apiRequest<DeleteFileImportResult>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}${query ? `?${query}` : ""}`,
    { method: "DELETE" },
  );
}
```

- [ ] **Step 2: ImpactAnalysisModal 支持自定义 report + destroyOnHidden**

```tsx
// frontend/src/components/ImpactAnalysisModal.tsx
// 1. destroyOnClose → destroyOnHidden
// 2. 扩展 props：
interface ImpactAnalysisModalProps {
  open: boolean;
  title?: string;
  loading?: boolean;
  report?: ImpactReport;
  counts?: Record<string, number>;  // 新增：直接传 published_counts
  totalCount?: number;
  onClose: () => void;
  onConfirm?: () => void;
  confirmText?: string;
  confirmLoading?: boolean;
}

// dataSource 优先使用 counts，否则 report.by_object_type
const dataSource = useMemo(() => {
  const source = counts ?? report?.by_object_type;
  if (!source) return [];
  return Object.entries(source).map(([key, count]) => ({
    key,
    object_type: key,
    label: OBJECT_TYPE_LABELS[key] ?? key,
    count,
  }));
}, [counts, report]);

// footer：onConfirm 存在时渲染确认/取消按钮
```

- [ ] **Step 3: FileImportCenter 删除流程**

在 `frontend/src/pages/FileImportCenter/index.tsx`：

```tsx
// state 追加
const [deleteImpactOpen, setDeleteImpactOpen] = useState(false);
const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
const [deleteConfirmLoading, setDeleteConfirmLoading] = useState(false);
const [pendingDeleteImport, setPendingDeleteImport] = useState<FileImportListItem | null>(null);
const [purgeImpact, setPurgeImpact] = useState<FileImportPurgeImpact | undefined>();

const handleDeleteClick = async (record: FileImportListItem, event: React.MouseEvent) => {
  event.stopPropagation();
  if (!selectedKbId) return;
  setPendingDeleteImport(record);
  setDeleteImpactLoading(true);
  setDeleteImpactOpen(true);
  try {
    const impact = await getFileImportPurgeImpact(selectedKbId, record.import_id);
    setPurgeImpact(impact);
    if (!impact.has_published_assets) {
      // 无已发布资产：关闭 modal，由 Popconfirm 处理（见 Step 4）
      setDeleteImpactOpen(false);
    }
  } catch (error) {
    message.error((error as Error).message);
    setDeleteImpactOpen(false);
    setPendingDeleteImport(null);
  } finally {
    setDeleteImpactLoading(false);
  }
};

const handleConfirmDeleteWithDeprecate = async () => {
  if (!selectedKbId || !pendingDeleteImport) return;
  setDeleteConfirmLoading(true);
  try {
    await deleteFileImport(selectedKbId, pendingDeleteImport.import_id, {
      deprecatePublished: true,
    });
    message.success("已删除，相关已发布资产已废弃");
    setDeleteImpactOpen(false);
    setPendingDeleteImport(null);
    void loadData();
  } catch (error) {
    message.error((error as Error).message);
  } finally {
    setDeleteConfirmLoading(false);
  }
};
```

删除按钮列改为：

```tsx
{purgeImpact && !purgeImpact.has_published_assets && pendingDeleteImport?.import_id === record.import_id ? (
  <Popconfirm
    title="确定删除该导入记录？"
    description="将删除导入文件及解析数据，不可恢复。"
    onConfirm={async () => { /* deleteFileImport 无 deprecatePublished */ }}
  >
    <Button size="small" danger onClick={(e) => void handleDeleteClick(record, e)}>删除</Button>
  </Popconfirm>
) : (
  <>
    <Button size="small" danger onClick={(e) => void handleDeleteClick(record, e)}>删除</Button>
    <ImpactAnalysisModal
      open={deleteImpactOpen && pendingDeleteImport?.import_id === record.import_id && !!purgeImpact?.has_published_assets}
      title="删除影响确认"
      loading={deleteImpactLoading}
      counts={purgeImpact?.published_counts}
      totalCount={purgeImpact?.published_total}
      onClose={() => { setDeleteImpactOpen(false); setPendingDeleteImport(null); }}
      onConfirm={() => void handleConfirmDeleteWithDeprecate()}
      confirmText="废弃已发布资产并删除"
      confirmLoading={deleteConfirmLoading}
    />
  </>
)}
```

简化实现建议：删除按钮统一 `onClick → handleDeleteClick`；无已发布时用 `Modal.confirm` 或保留 Popconfirm wrapper；有已发布时打开 `ImpactAnalysisModal`。

- [ ] **Step 4: 手动验证**

1. 启动 backend + frontend
2. 删除仅有候选数据的 import → 成功，列表消失
3. 删除有已发布 KU 的 import → 弹出影响 Modal → 确认后成功，KU 变 deprecated

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/fileImports.ts frontend/src/pages/FileImportCenter/index.tsx frontend/src/components/ImpactAnalysisModal.tsx
git commit -m "feat: file import delete flow with published asset confirmation"
```

---

## Task 6: antd destroyOnHidden 批量修复

**Files:**
- Modify: 7 个前端文件（见 File Map）

- [ ] **Step 1: 全局替换**

在每个文件的 Modal / Drawer 上将 `destroyOnClose` 改为 `destroyOnHidden`：

```
frontend/src/components/MergeWizard.tsx
frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx
frontend/src/pages/FileImportCenter/TaskLogDrawer.tsx
frontend/src/pages/KnowledgeBaseList/index.tsx
frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx
frontend/src/pages/TemplateLibraryCenter/PublishModal.tsx
```

（`ImpactAnalysisModal.tsx` 已在 Task 5 处理）

- [ ] **Step 2: 前端构建验证**

Run: `cd frontend && npm run build`

Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MergeWizard.tsx frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx frontend/src/pages/FileImportCenter/TaskLogDrawer.tsx frontend/src/pages/KnowledgeBaseList/index.tsx frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx frontend/src/pages/TemplateLibraryCenter/PublishModal.tsx
git commit -m "fix: replace antd destroyOnClose with destroyOnHidden"
```

---

## Task 7: 全量回归 + 设计文档状态更新

**Files:**
- Modify: `docs/superpowers/specs/2026-06-14-file-import-delete-fix-design.md`

- [ ] **Step 1: 运行后端测试**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py tests/contract/test_file_import_delete.py tests/contract/test_file_import_upload.py -v`

Expected: 全部 PASS

- [ ] **Step 2: 更新 spec 状态**

```markdown
**Status**: Approved
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-14-file-import-delete-fix-design.md
git commit -m "docs: mark file import delete fix spec approved"
```

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| FileImportStatus.deleted | Task 1 |
| purge-impact API | Task 2, 4 |
| DELETE deprecate_published | Task 3, 4 |
| 409 PUBLISHED_ASSETS_EXIST + details | Task 3, 4 |
| 墓碑化非物理 DELETE | Task 3 |
| 废弃 + IndexBuilder deprecate | Task 3 |
| detach source_doc 避免 FK | Task 3 |
| document_media_assets 清理 | Task 3 |
| list 过滤 deleted | Task 4 |
| IntegrityError → 409 | Task 4 |
| 前端分岔删除 UX | Task 5 |
| destroyOnHidden | Task 5, 6 |
| 契约/单元测试 | Task 2–4, 7 |
