# Import Hard Purge + Table Sidecar + V2 Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成来源导入硬删除全链清理、tender_skills 表格侧车 seed、以及 V2 全量重命名，使测试文件可反复上传且知识数据无残留。

**Architecture:** 分 3 个 PR 交付：PR1 重写 `file_import_purge_service`（按 FK 顺序硬删 + 存储清理）；PR2 升级 `doc-chunk` 依赖并在 `asset_seed_service` 读取 `tables/` 侧车；PR3 机械 rename 前后端 `knowledge_v2`/`KnowledgeV2` 为 `knowledge`/`Knowledge`。每 PR 独立 pytest/vitest 绿。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pytest, httpx | React 18, TypeScript, Ant Design 5, Vite | tender_skills (`doc-chunk` path dep)

**Design doc:** `docs/superpowers/specs/2026-06-21-import-purge-v2-rename-tender-skills-design.md`

---

## File Map

| 路径 | 职责 | PR |
|------|------|-----|
| `backend/src/services/file_import_purge_service.py` | 硬删除 purge 核心 | 1 |
| `backend/src/api/routes/file_imports.py` | DELETE / purge-impact API | 1 |
| `backend/tests/unit/test_file_import_purge_service.py` | purge 单元测试 | 1 |
| `backend/tests/contract/test_file_import_delete.py` | DELETE 契约测试 | 1 |
| `frontend/src/services/fileImports.ts` | purge-impact 类型、delete API | 1 |
| `frontend/src/pages/FileImportCenter/index.tsx` | 简化删除 UX | 1 |
| `backend/pyproject.toml` | doc-chunk 依赖 | 2 |
| `backend/src/services/knowledge_v2/asset_seed_service.py` | table sidecar seed | 2 |
| `backend/tests/fixtures/doc_chunk_workspace_minimal/tables/` | 侧车 fixture | 2 |
| `backend/tests/unit/test_knowledge_v2_asset_seed.py` | sidecar 测试 | 2 |
| `backend/src/services/knowledge/` | rename from knowledge_v2 | 3 |
| `frontend/src/pages/Knowledge/` | rename from KnowledgeV2 | 3 |
| `frontend/src/components/Knowledge/` | rename from KnowledgeV2 | 3 |
| `frontend/src/App.tsx`, `layout/AppShell.tsx` | 路由与导航 | 3 |

---

# PR1 — 来源导入硬删除

## Task 1: purge-impact 单元测试（knowledge_chunks 计数）

**Files:**
- Create: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: 写失败测试**

```python
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.file_import_purge_service import check_purge_impact


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
    db_session.add(
        KnowledgeChunk(
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
            regions=[],
            content_hash="abc123",
            token_count=1,
        )
    )
    db_session.commit()

    report = check_purge_impact(db_session, kb_id=seeded_kb.kb_id, import_id=import_id)
    assert report.intermediate_counts["knowledge_chunks"] >= 1
    assert report.has_published_assets is False
```

- [ ] **Step 2: 运行确认 FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py::test_check_purge_impact_counts_knowledge_chunks -v`  
Expected: FAIL — `intermediate_counts['knowledge_chunks']` KeyError 或计数为 0

- [ ] **Step 3: 更新 `PurgeImpactReport` 与 `check_purge_impact`**

Modify `backend/src/services/file_import_purge_service.py`:

```python
@dataclass
class PurgeImpactReport:
    import_id: str
    file_name: str
    has_published_assets: bool = False  # 保留字段，恒为 False，兼容旧前端直到 PR1 前端更新
    published_counts: dict[str, int] = field(default_factory=dict)
    published_total: int = 0
    intermediate_counts: dict[str, int] = field(default_factory=dict)
```

在 `check_purge_impact` 中补充计数：

```python
document_ids = [row.document_id for row in db.query(Document).filter(Document.import_id == import_id).all()]
chunk_count = (
    db.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id.in_(document_ids)).count()
    if document_ids
    else 0
)
asset_count = (
    db.query(ChunkAsset).filter(ChunkAsset.doc_id.in_(document_ids)).count()
    if document_ids
    else 0
)
embedding_count = 0
if document_ids:
    chunk_ids = [row.id for row in db.query(KnowledgeChunk.id).filter(KnowledgeChunk.doc_id.in_(document_ids)).all()]
    asset_ids = [row.id for row in db.query(ChunkAsset.id).filter(ChunkAsset.doc_id.in_(document_ids)).all()]
    from sqlalchemy import or_, and_
    filters = []
    if chunk_ids:
        filters.append(and_(ChunkEmbedding.object_type == "chunk", ChunkEmbedding.object_id.in_(chunk_ids)))
    if asset_ids:
        filters.append(and_(ChunkEmbedding.object_type == "asset", ChunkEmbedding.object_id.in_(asset_ids)))
    if filters:
        embedding_count = db.query(ChunkEmbedding).filter(or_(*filters)).count()

return PurgeImpactReport(
    ...
    intermediate_counts={
        "documents": doc_count,
        "import_tasks": task_count,
        "knowledge_chunks": chunk_count,
        "chunk_assets": asset_count,
        "chunk_embeddings": embedding_count,
        "actual_bid_parse_tasks": db.query(ActualBidParseTask).filter(ActualBidParseTask.import_id == import_id).count(),
    },
)
```

添加 imports：`KnowledgeChunk`, `ChunkAsset`, `ChunkEmbedding`, `ActualBidParseTask`。

- [ ] **Step 4: 运行确认 PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py::test_check_purge_impact_counts_knowledge_chunks -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/file_import_purge_service.py backend/tests/unit/test_file_import_purge_service.py
git commit -m "test: add purge-impact counts for knowledge chunks"
```

---

## Task 2: 硬删除 purge 核心逻辑

**Files:**
- Modify: `backend/src/services/file_import_purge_service.py`
- Modify: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: 写失败测试 — 硬删 file_import 行**

```python
def test_purge_file_import_hard_deletes_row(db_session, seeded_kb):
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
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    assert summary.status == "deleted"
    assert db_session.get(FileImport, import_id) is None
    assert summary.deleted_counts.get("file_imports") == 1
```

- [ ] **Step 2: 写失败测试 — 清理 knowledge_chunks**

```python
def test_purge_file_import_deletes_knowledge_chunks(db_session, seeded_kb):
    # ... 同 Task 1 创建 imp + doc + KnowledgeChunk ...
    purge_file_import(db_session, kb_id=seeded_kb.kb_id, import_id=import_id, operator_id="admin", trace_id=None)
    db_session.commit()
    assert db_session.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id == doc.document_id).count() == 0
```

- [ ] **Step 3: 写失败测试 — 存储目录清理**

```python
from pathlib import Path
from src.config import Settings

def test_purge_file_import_removes_storage_dirs(db_session, seeded_kb, storage_root_tmp, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root_tmp))
    import_id = uuid4()
    # ... 创建 imp + doc ...
    import_dir = storage_root_tmp / str(seeded_kb.kb_id) / str(import_id)
    import_dir.mkdir(parents=True)
    (import_dir / "upload.docx").write_bytes(b"x")
    doc_dir = storage_root_tmp / "documents" / str(doc.document_id)
    doc_dir.mkdir(parents=True)
    (doc_dir / "content.md").write_text("# hi", encoding="utf-8")
    workspace_dir = storage_root_tmp / "doc_chunk_workspaces" / str(seeded_kb.kb_id) / str(import_id)
    workspace_dir.mkdir(parents=True)

    purge_file_import(db_session, kb_id=seeded_kb.kb_id, import_id=import_id, operator_id="admin", trace_id=None)
    db_session.commit()

    assert not import_dir.exists()
    assert not doc_dir.exists()
    assert not workspace_dir.exists()
```

- [ ] **Step 4: 运行 — expect FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py -v`  
Expected: FAIL on hard delete / chunk cleanup / storage

- [ ] **Step 5: 重写 `purge_file_import`**

核心 helper（写入 `file_import_purge_service.py`）：

```python
def _collect_import_ids(db: Session, *, kb_id: UUID, import_id: UUID) -> list[UUID]:
    """含子 import（parent_import_id 指向本 import），先子后父顺序。"""
    child_ids = [
        row.import_id
        for row in db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.parent_import_id == import_id)
        .all()
    ]
    ordered: list[UUID] = []
    for child in child_ids:
        ordered.extend(_collect_import_ids(db, kb_id=kb_id, import_id=child))
    ordered.append(import_id)
    return ordered


def _purge_documents_for_import(db: Session, *, document_ids: list[UUID], counts: dict[str, int]) -> None:
    if not document_ids:
        return
    chunk_ids = [row.id for row in db.query(KnowledgeChunk.id).filter(KnowledgeChunk.doc_id.in_(document_ids)).all()]
    asset_ids = [row.id for row in db.query(ChunkAsset.id).filter(ChunkAsset.doc_id.in_(document_ids)).all()]
    from sqlalchemy import or_, and_
    emb_filters = []
    if chunk_ids:
        emb_filters.append(and_(ChunkEmbedding.object_type == "chunk", ChunkEmbedding.object_id.in_(chunk_ids)))
    if asset_ids:
        emb_filters.append(and_(ChunkEmbedding.object_type == "asset", ChunkEmbedding.object_id.in_(asset_ids)))
    if emb_filters:
        _inc(counts, "chunk_embeddings", db.query(ChunkEmbedding).filter(or_(*emb_filters)).delete(synchronize_session=False))
    _inc(counts, "chunk_assets", db.query(ChunkAsset).filter(ChunkAsset.doc_id.in_(document_ids)).delete(synchronize_session=False))
    _inc(counts, "knowledge_chunks", db.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id.in_(document_ids)).delete(synchronize_session=False))
    _inc(counts, "document_parse_suggestions", db.query(DocumentParseSuggestion).filter(DocumentParseSuggestion.document_id.in_(document_ids)).delete(synchronize_session=False))
    _inc(counts, "document_tree_nodes", db.query(DocumentTreeNode).filter(DocumentTreeNode.document_id.in_(document_ids)).delete(synchronize_session=False))
    _inc(counts, "document_media_assets", db.query(DocumentMediaAsset).filter(DocumentMediaAsset.document_id.in_(document_ids)).delete(synchronize_session=False))
    _inc(counts, "documents", db.query(Document).filter(Document.document_id.in_(document_ids)).delete(synchronize_session=False))


def _delete_document_storage(document_ids: list[UUID], *, storage_root: Path) -> int:
    removed = 0
    for doc_id in document_ids:
        path = storage_root / "documents" / str(doc_id)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed
```

`purge_file_import` 主流程：

```python
def purge_file_import(...) -> PurgeSummary:
    record = db.query(FileImport).filter(...).one_or_none()
    if record is None:
        raise FileImportPurgeServiceError(...)
    # 不再 early-return deleted 墓碑；行不存在即 NOT_FOUND

    import_ids = _collect_import_ids(db, kb_id=kb_id, import_id=import_id)
    counts: dict[str, int] = {}
    # audit log（保留 import_id 引用直至删除前写入）
    db.add(ImportAuditLog(..., action=ImportAuditAction.delete, ...))

    for iid in import_ids:
        document_ids = [row.document_id for row in db.query(Document).filter(Document.import_id == iid).all()]
        _purge_documents_for_import(db, document_ids=document_ids, counts=counts)
        _inc(counts, "actual_bid_parse_tasks", db.query(ActualBidParseTask).filter(ActualBidParseTask.import_id == iid).delete(synchronize_session=False))
        _inc(counts, "downstream_task_entries", ...)
        _inc(counts, "import_tasks", ...)
        _inc(counts, "file_purpose_suggestions", ...)
        if _delete_storage_dir(kb_id, iid):
            _inc(counts, "storage_dirs", 1)
        ws_path = Path(Settings().storage_root) / "doc_chunk_workspaces" / str(kb_id) / str(iid)
        if ws_path.exists():
            shutil.rmtree(ws_path, ignore_errors=True)
            _inc(counts, "doc_chunk_workspaces", 1)
        _inc(counts, "document_storage_dirs", _delete_document_storage(document_ids, storage_root=Path(Settings().storage_root)))
        deleted = db.query(FileImport).filter(FileImport.kb_id == kb_id, FileImport.import_id == iid).delete(synchronize_session=False)
        _inc(counts, "file_imports", deleted)

    db.flush()
    return PurgeSummary(import_id=str(import_id), file_name=record.file_name, status="deleted", deleted_counts=counts)
```

移除 `deprecate_published` 参数及 payload 中的 `deprecate_published` 字段。

- [ ] **Step 6: 运行 — expect PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/services/file_import_purge_service.py backend/tests/unit/test_file_import_purge_service.py
git commit -m "feat: hard-delete file imports with full knowledge chunk purge"
```

---

## Task 3: API 路由更新

**Files:**
- Modify: `backend/src/api/routes/file_imports.py`
- Create: `backend/tests/contract/test_file_import_delete.py`

- [ ] **Step 1: 写契约测试**

```python
def test_delete_file_import_returns_deleted_counts(client, seeded_kb, db_session):
    imp = _seed_minimal_import(db_session, seeded_kb.kb_id)
    db_session.commit()
    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "deleted"
    assert body["deleted_counts"]["file_imports"] >= 1
    listed = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports")
    assert all(item["import_id"] != str(imp.import_id) for item in listed.json()["data"]["items"])
```

- [ ] **Step 2: 修改 DELETE 路由**

Remove `deprecate_published: bool = False` from `delete_file_import`; call `purge_file_import(...)` without that arg.

Optional: remove `FileImport.status != FileImportStatus.deleted` from `list_file_imports`（硬删后无墓碑，保留过滤亦无害）。

- [ ] **Step 3: 运行契约测试**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_file_import_delete.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/api/routes/file_imports.py backend/tests/contract/test_file_import_delete.py
git commit -m "feat: simplify file import DELETE to hard purge"
```

---

## Task 4: 前端删除 UX 简化

**Files:**
- Modify: `frontend/src/services/fileImports.ts`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`

- [ ] **Step 1: 更新 TypeScript 类型**

```typescript
export interface FileImportPurgeImpact {
  import_id: string;
  file_name: string;
  intermediate_counts: Record<string, number>;
}

export async function deleteFileImport(
  kbId: string,
  importId: string,
): Promise<DeleteFileImportResult> {
  return apiRequest<DeleteFileImportResult>(
    `/api/v1/kbs/${kbId}/file-imports/${importId}`,
    { method: "DELETE" },
  );
}
```

移除 `deprecatePublished` 参数及 `has_published_assets` / `published_*` 字段。

- [ ] **Step 2: 简化 `FileImportCenter` 删除流程**

- 删除 `ImpactAnalysisModal` import 与 JSX
- 删除 state：`deleteImpactOpen`, `pendingDeleteImport`, `deleteConfirmLoading`（若仅用于废弃流程）
- `handleDeleteClick` 改为：

```typescript
const handleDeleteClick = useCallback(
  async (record: FileImportListItem) => {
    if (!selectedKbId) return;
    let impactText = "将删除导入文件、解析数据及已录入知识，不可恢复。";
    try {
      const impact = await getFileImportPurgeImpact(selectedKbId, record.import_id);
      const c = impact.intermediate_counts;
      const parts = [
        c.knowledge_chunks ? `${c.knowledge_chunks} 条知识` : null,
        c.documents ? `${c.documents} 个文档` : null,
      ].filter(Boolean);
      if (parts.length) {
        impactText = `将删除 ${parts.join("、")} 及导入文件，不可恢复。`;
      }
    } catch {
      /* fallback to default text */
    }
    Modal.confirm({
      title: "确定删除该导入记录？",
      content: impactText,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await deleteFileImport(selectedKbId, record.import_id);
        message.success("已删除");
        void loadData();
      },
    });
  },
  [loadData, selectedKbId],
);
```

- 更新解析完成链接（若仍为 v2）：`/knowledge-v2/entry` → 暂不改，PR3 统一改

- [ ] **Step 3: 运行前端测试（如有）**

Run: `cd frontend && npm test -- --run 2>/dev/null || true`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/fileImports.ts frontend/src/pages/FileImportCenter/index.tsx
git commit -m "refactor: simplify file import delete UX for hard purge"
```

---

## Task 5: PR1 验收

- [ ] **Step 1: 后端全量**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py tests/contract/test_file_import_delete.py -v`  
Expected: PASS

- [ ] **Step 2: 手动冒烟（可选）**

上传 docx → 解析 → 录入一条 chunk → 删除 → 确认浏览页为空 → 重新上传同文件成功

---

# PR2 — tender_skills 表格侧车

## Task 6: 升级 doc-chunk 依赖

**Files:**
- Modify: `backend/pyproject.toml`（路径已指向 `../../tender_skills`，确认最新）
- Shell: reinstall

- [ ] **Step 1: 重装依赖**

```bash
cd /Users/tongqianni/xlab/tender_skills && git pull
cd /Users/tongqianni/xlab/tender_knowledge/backend && ../.venv/bin/pip install -e ".[dev]" -e "../../tender_skills[dev]"
```

- [ ] **Step 2: 验证 doc_chunk 可导入**

Run: `cd backend && ../.venv/bin/python -c "from doc_chunk.table.access import load_table_model; print('ok')"`  
Expected: `ok`

- [ ] **Step 3: Commit（若 pyproject 有变）**

```bash
git commit -m "chore: reinstall tender_skills with table sidecar support"
```

---

## Task 7: 扩展 fixture — tables 侧车

**Files:**
- Create: `backend/tests/fixtures/doc_chunk_workspace_minimal/tables/t0000.json`
- Create: `backend/tests/fixtures/doc_chunk_workspace_minimal/tables/index.json`
- Modify: `backend/tests/fixtures/doc_chunk_workspace_minimal/content.blocks.json`（为 table 块加 `table_ref`）

- [ ] **Step 1: 添加侧车 JSON**

`tables/t0000.json` 示例：

```json
{
  "schema_version": "1.0",
  "block_index": 3,
  "layout_type": "simple",
  "grid_width": 2,
  "grid": {"rows": []},
  "logical_rows": [["列A", "列B"], ["1", "2"]],
  "markdown": "|列A|列B|\n|---|---|\n|1|2|",
  "llm_text": "【表格:示例】列A=1; 列B=2",
  "record_groups": [],
  "records": []
}
```

`tables/index.json`:

```json
{"schema_version": "1.0", "tables": [{"block_index": 3, "path": "tables/t0000.json"}]}
```

在 `content.blocks.json` 对应 table 块增加 `"table_ref": "tables/t0000.json"`。

- [ ] **Step 2: Commit fixture**

```bash
git add backend/tests/fixtures/doc_chunk_workspace_minimal/
git commit -m "test: add table sidecar fixture for asset seed"
```

---

## Task 8: asset_seed_service 侧车适配（TDD）

**Files:**
- Modify: `backend/src/services/knowledge_v2/asset_seed_service.py`
- Modify: `backend/tests/unit/test_knowledge_v2_asset_seed.py`

- [ ] **Step 1: 写失败测试**

```python
def test_seed_chunk_assets_uses_table_sidecar(db_session, seeded_kb, tmp_path):
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE_ROOT, workspace)
    doc_id = uuid4()
    count = seed_chunk_assets_from_workspace(
        db_session, kb_id=seeded_kb.kb_id, doc_id=doc_id, workspace_path=workspace
    )
    table_rows = (
        db_session.query(ChunkAsset)
        .filter(ChunkAsset.doc_id == doc_id, ChunkAsset.asset_type == "table")
        .all()
    )
    assert len(table_rows) >= 1
    row = table_rows[0]
    assert row.table_schema is not None
    assert row.table_schema.get("layout_type") == "simple"
    assert row.raw_markdown == "|列A|列B|\n|---|---|\n|1|2|"
    assert row.table_summary == "【表格:示例】列A=1; 列B=2"
    assert row.table_headers == ["列A", "列B"]
    assert row.table_rows == [["1", "2"]]
```

- [ ] **Step 2: 运行 — expect FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_v2_asset_seed.py::test_seed_chunk_assets_uses_table_sidecar -v`  
Expected: FAIL — `table_schema is None`

- [ ] **Step 3: 实现侧车加载**

在 `asset_seed_service.py` 添加：

```python
def _load_blocks_index(workspace: Path) -> dict[int, str]:
    payload = _load_json(workspace / "content.blocks.json") or {}
    mapping: dict[int, str] = {}
    for block in payload.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        table_ref = block.get("table_ref")
        block_index = block.get("block_index")
        if table_ref and isinstance(block_index, int):
            mapping[block_index] = str(table_ref)
    return mapping


def _load_table_sidecar(workspace: Path, table_ref: str) -> dict[str, Any] | None:
    path = workspace / table_ref
    payload = _load_json(path)
    return payload if isinstance(payload, dict) else None


def _table_asset_fields(sidecar: dict[str, Any]) -> dict[str, Any]:
    logical_rows = sidecar.get("logical_rows") or []
    headers = logical_rows[0] if logical_rows else None
    body_rows = logical_rows[1:] if len(logical_rows) > 1 else []
    return {
        "raw_markdown": sidecar.get("markdown"),
        "table_summary": sidecar.get("llm_text"),
        "table_schema": {
            "schema_version": sidecar.get("schema_version"),
            "layout_type": sidecar.get("layout_type"),
            "grid_width": sidecar.get("grid_width"),
            "record_groups": sidecar.get("record_groups") or [],
        },
        "table_headers": headers,
        "table_rows": body_rows,
    }
```

处理 chunk table block 时：

```python
table_ref = block.get("table_ref")
if not table_ref:
    block_index = block.get("block_index")
    if isinstance(block_index, int):
        table_ref = blocks_index.get(block_index)
sidecar = _load_table_sidecar(workspace, table_ref) if table_ref else None
fields = _table_asset_fields(sidecar) if sidecar else {
    "raw_markdown": markdown or None,
}
db.add(ChunkAsset(..., asset_type="table", char_start=..., char_end=..., **fields))
```

在 `seed_chunk_assets_from_workspace` 开头：`blocks_index = _load_blocks_index(workspace)`。

- [ ] **Step 4: 运行 — expect PASS**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_v2_asset_seed.py -v`  
Expected: PASS（含旧 table fallback 测试）

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge_v2/asset_seed_service.py backend/tests/unit/test_knowledge_v2_asset_seed.py
git commit -m "feat: seed chunk table assets from doc_chunk table sidecars"
```

---

## Task 9: PR2 回归

- [ ] **Step 1: doc_chunk 相关测试**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_v2_asset_seed.py tests/unit/test_doc_chunk_import_service.py -v`  
Expected: PASS

---

# PR3 — V2 全量重命名

## Task 10: 后端 knowledge_v2 → knowledge

**Files:**
- Rename: `backend/src/services/knowledge_v2/` → `backend/src/services/knowledge/`
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/src/services/doc_chunk/import_service.py`
- Rename tests: `backend/tests/unit/test_knowledge_v2_*.py` → `test_knowledge_*.py`
- Rename: `backend/tests/integration/test_knowledge_v2_*.py`

- [ ] **Step 1: git mv 目录**

```bash
cd backend
git mv src/services/knowledge_v2 src/services/knowledge
for f in tests/unit/test_knowledge_v2_*.py; do
  git mv "$f" "${f/knowledge_v2/knowledge}"
done
git mv tests/integration/test_knowledge_v2_api.py tests/integration/test_knowledge_api.py
git mv tests/integration/test_knowledge_v2_flow.py tests/integration/test_knowledge_flow.py
```

- [ ] **Step 2: 批量替换 import**

```bash
cd backend
rg -l 'knowledge_v2' src tests | xargs sed -i '' 's/knowledge_v2/knowledge/g'
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_*.py tests/integration/test_knowledge_*.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A backend/
git commit -m "refactor: rename knowledge_v2 package to knowledge"
```

---

## Task 11: 前端 KnowledgeV2 → Knowledge

**Files:**
- Rename: `frontend/src/pages/KnowledgeV2/` → `pages/Knowledge/`
- Rename: `frontend/src/components/KnowledgeV2/` → `components/Knowledge/`
- Modify: `frontend/src/App.tsx`, `frontend/src/layout/AppShell.tsx`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`
- Modify: `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx`（localStorage key）

- [ ] **Step 1: git mv**

```bash
cd frontend/src
git mv pages/KnowledgeV2 pages/Knowledge
git mv components/KnowledgeV2 components/Knowledge
```

- [ ] **Step 2: 更新路由与导航**

`App.tsx`:

```tsx
import KnowledgeEntryPage from "./pages/Knowledge/KnowledgeEntryPage";
import KnowledgeBrowsePage from "./pages/Knowledge/KnowledgeBrowsePage";
// ...
<Route path="/knowledge/entry" element={<KnowledgeEntryPage />} />
<Route path="/knowledge/browse" element={<KnowledgeBrowsePage />} />
```

`AppShell.tsx`:

```tsx
{ key: "/knowledge/entry", label: <Link to="/knowledge/entry">知识录入</Link> },
{ key: "/knowledge/browse", label: <Link to="/knowledge/browse">知识浏览</Link> },
```

- [ ] **Step 3: 更新内部 import 路径**

```bash
cd frontend
rg -l 'KnowledgeV2|knowledge-v2' src | xargs sed -i '' \
  -e 's|components/KnowledgeV2|components/Knowledge|g' \
  -e 's|pages/KnowledgeV2|pages/Knowledge|g' \
  -e 's|/knowledge-v2/|/knowledge/|g' \
  -e 's|knowledge-v2-filters|knowledge-filters|g' \
  -e 's|知识录入 V2|知识录入|g' \
  -e 's|知识浏览 V2|知识浏览|g'
```

- [ ] **Step 4: 运行 vitest**

Run: `cd frontend && npm test -- --run`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A frontend/
git commit -m "refactor: rename KnowledgeV2 UI to Knowledge routes and labels"
```

---

## Task 12: 全库 grep 清零与 PR3 验收

- [ ] **Step 1: 确认无残留 V2 引用（代码）**

Run: `rg 'knowledge_v2|KnowledgeV2|knowledge-v2' backend/src frontend/src backend/tests --glob '!docs/**'`  
Expected: 无匹配（或仅注释/历史字符串）

- [ ] **Step 2: 全量测试**

Run: `cd backend && ../.venv/bin/pytest -q`  
Run: `cd frontend && npm test -- --run`

- [ ] **Step 3: 手动通路**

上传 → 解析 → 「前往知识录入」(`/knowledge/entry`) → 入库 → `/knowledge/browse` 可见 → 删除 import → 浏览为空

---

## Spec Coverage Checklist

| Spec § | Task |
|--------|------|
| §3 硬删除顺序 | Task 2 |
| §3.3 API 移除 deprecate_published | Task 3 |
| §3.4 前端单次 confirm | Task 4 |
| §3.5 purge 测试 | Tasks 1–3 |
| §5.1 依赖升级 | Task 6 |
| §5.2 sidecar seed | Tasks 7–8 |
| §5.4 sidecar 测试 | Task 8 |
| §4 全量 rename | Tasks 10–12 |
| §6 三 PR 顺序 | PR1 Tasks 1–5, PR2 Tasks 6–9, PR3 Tasks 10–12 |
