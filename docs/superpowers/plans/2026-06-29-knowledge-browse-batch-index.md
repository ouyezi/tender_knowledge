# 知识浏览页批量构建索引 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在知识浏览页为列表模式与语义搜索模式增加多选与「批量构建索引」，非阻塞提交 + 轮询进度，取消时将未完成项标为 `failed`。

**Architecture:** 前端在 `KnowledgeBrowsePage` 用 `rowSelection` 与 `batchIndex` 状态机并发调用现有单条 index API，轮询 `embedding_status`；后端新增 `mark-index-failed` 批量接口，并在 `index_knowledge_chunk` 写入终态前检查是否仍为 `indexing`，防止取消后被覆盖。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（backend）；React + Ant Design Table + Vitest（frontend）

**Spec:** `docs/superpowers/specs/2026-06-29-knowledge-browse-batch-index-design.md`

---

## File Map

| File | Responsibility |
|------|----------------|
| `backend/src/services/knowledge/chunk_service.py` | 新增 `mark_chunks_index_failed` 服务函数 |
| `backend/src/services/knowledge/chunk_index_task.py` | 终态写入前取消防护 |
| `backend/src/api/schemas/knowledge_chunks.py` | `MarkChunksIndexFailedRequest` schema |
| `backend/src/api/routes/knowledge_chunks.py` | `POST .../mark-index-failed` 路由（须在 `/{chunk_id}/index` 之前） |
| `backend/tests/unit/test_mark_chunks_index_failed.py` | 服务层单元测试 |
| `backend/tests/unit/test_chunk_index_task.py` | 取消防护单元测试 |
| `backend/tests/integration/test_knowledge_api.py` | mark-failed API 集成测试 |
| `frontend/src/pages/Knowledge/batchIndexUtils.ts` | 分区、并发工具 |
| `frontend/src/pages/Knowledge/batchIndexUtils.test.ts` | 工具函数 Vitest |
| `frontend/src/services/knowledgeChunks.ts` | 导出终态集合、`markChunksIndexFailed` |
| `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx` | 多选 UI、批量状态机、进度条 |

---

### Task 1: `mark_chunks_index_failed` 服务层

**Files:**
- Modify: `backend/src/services/knowledge/chunk_service.py`（文件末尾追加）
- Create: `backend/tests/unit/test_mark_chunks_index_failed.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_mark_chunks_index_failed.py
from __future__ import annotations

from uuid import uuid4

from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_service import mark_chunks_index_failed
from tests.helpers.chunk_payload import minimal_chunk_orm_kwargs


def _seed_chunk(db_session, kb_id, *, chunk_id: int, embedding_status: str = "indexing"):
    chunk = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        doc_id=uuid4(),
        primary_node_id=str(uuid4()),
        content_hash=f"hash-{chunk_id}",
        token_count=3,
        embedding_status=embedding_status,
        **minimal_chunk_orm_kwargs(),
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk


def test_mark_chunks_index_failed_updates_only_indexing(db_session, seeded_kb):
    indexing = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=1, embedding_status="indexing")
    ready = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=2, embedding_status="ready")

    result = mark_chunks_index_failed(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_ids=[indexing.id, ready.id, 999],
    )

    assert result.updated_ids == [1]
    assert sorted(result.skipped_ids) == [2, 999]
    db_session.refresh(indexing)
    db_session.refresh(ready)
    assert indexing.embedding_status == "failed"
    assert ready.embedding_status == "ready"


def test_mark_chunks_index_failed_respects_kb_isolation(db_session, seeded_kb):
    other_kb_id = uuid4()
    chunk = _seed_chunk(db_session, other_kb_id, chunk_id=10, embedding_status="indexing")

    result = mark_chunks_index_failed(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_ids=[chunk.id],
    )

    assert result.updated_ids == []
    assert result.skipped_ids == [10]
    db_session.refresh(chunk)
    assert chunk.embedding_status == "indexing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_mark_chunks_index_failed.py -v`

Expected: FAIL with `ImportError: cannot import name 'mark_chunks_index_failed'`

- [ ] **Step 3: Write minimal implementation**

在 `backend/src/services/knowledge/chunk_service.py` 顶部 import 区追加：

```python
from dataclasses import dataclass
```

在文件末尾追加：

```python
@dataclass
class MarkIndexFailedResult:
    updated_ids: list[int]
    skipped_ids: list[int]


def mark_chunks_index_failed(
    db: Session,
    *,
    kb_id: UUID,
    chunk_ids: list[int],
) -> MarkIndexFailedResult:
    if not chunk_ids:
        return MarkIndexFailedResult(updated_ids=[], skipped_ids=[])

    requested = list(dict.fromkeys(chunk_ids))
    rows = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.id.in_(requested))
        .all()
    )
    by_id = {row.id: row for row in rows}
    updated_ids: list[int] = []
    skipped_ids: list[int] = []

    for chunk_id in requested:
        row = by_id.get(chunk_id)
        if row is None or row.embedding_status != "indexing":
            skipped_ids.append(chunk_id)
            continue
        row.embedding_status = "failed"
        updated_ids.append(chunk_id)

    if updated_ids:
        db.commit()
    return MarkIndexFailedResult(updated_ids=updated_ids, skipped_ids=skipped_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_mark_chunks_index_failed.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_service.py backend/tests/unit/test_mark_chunks_index_failed.py
git commit -m "feat(knowledge): add mark_chunks_index_failed service"
```

---

### Task 2: `mark-index-failed` API 路由

**Files:**
- Modify: `backend/src/api/schemas/knowledge_chunks.py`
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/tests/integration/test_knowledge_api.py`

- [ ] **Step 1: Write the failing integration test**

在 `backend/tests/integration/test_knowledge_api.py` 末尾追加：

```python
def test_mark_chunks_index_failed_api(client, db_session, seeded_kb):
    from uuid import uuid4

    from src.models.knowledge_chunk import KnowledgeChunk
    from tests.helpers.chunk_payload import minimal_chunk_orm_kwargs

    chunk = KnowledgeChunk(
        id=501,
        kb_id=seeded_kb.kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        doc_id=uuid4(),
        primary_node_id=str(uuid4()),
        content_hash="hash-501",
        token_count=3,
        embedding_status="indexing",
        **minimal_chunk_orm_kwargs(),
    )
    db_session.add(chunk)
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/mark-index-failed",
        json={"chunk_ids": [501, 502]},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["updated_ids"] == [501]
    assert body["skipped_ids"] == [502]

    db_session.refresh(chunk)
    assert chunk.embedding_status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_knowledge_api.py::test_mark_chunks_index_failed_api -v`

Expected: FAIL with 404 Not Found

- [ ] **Step 3: Add schema**

在 `backend/src/api/schemas/knowledge_chunks.py` 的 `IndexKnowledgeChunkRequest` 之后追加：

```python
class MarkChunksIndexFailedRequest(BaseModel):
    chunk_ids: list[int] = Field(..., min_length=1, max_length=200)
```

- [ ] **Step 4: Add route（放在 `@router.post("/{chunk_id}/index")` 之前）**

在 `backend/src/api/routes/knowledge_chunks.py` import 区：

```python
from src.api.schemas.knowledge_chunks import (
    ...
    MarkChunksIndexFailedRequest,
)
from src.services.knowledge.chunk_service import (
  ...
  mark_chunks_index_failed,
)
```

在 `@router.post("/{chunk_id}/index")` **之前**插入：

```python
@router.post("/mark-index-failed")
def mark_chunks_index_failed_api(
    kb_id: UUID,
    body: MarkChunksIndexFailedRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    result = mark_chunks_index_failed(db, kb_id=kb_id, chunk_ids=body.chunk_ids)
    return success(
        {
            "updated_ids": result.updated_ids,
            "skipped_ids": result.skipped_ids,
        },
        trace_id=get_trace_id(),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_knowledge_api.py::test_mark_chunks_index_failed_api -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/schemas/knowledge_chunks.py backend/src/api/routes/knowledge_chunks.py backend/tests/integration/test_knowledge_api.py
git commit -m "feat(api): add mark-index-failed endpoint for batch index cancel"
```

---

### Task 3: 索引任务取消防护

**Files:**
- Modify: `backend/src/services/knowledge/chunk_index_task.py`
- Modify: `backend/tests/unit/test_chunk_index_task.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/unit/test_chunk_index_task.py` 末尾追加：

```python
def test_index_knowledge_chunk_does_not_overwrite_cancelled_failed(
    db_session, seeded_kb, monkeypatch
):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)

    def fake_rewrite(**_):
        chunk.embedding_status = "failed"
        db_session.commit()
        return {"summary": "新摘要", "date_confidence": "low"}

    monkeypatch.setattr(
        "src.services.knowledge.chunk_index_task.rewrite_chunk_summary",
        fake_rewrite,
    )

    def fake_embed_text(_self, text: str) -> EmbeddingResult:
        return EmbeddingResult(vector=[0.1, 0.2, 0.3])

    monkeypatch.setattr(
        "src.services.knowledge.chunk_index_task.EmbeddingClient.embed_text",
        fake_embed_text,
    )
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://embedding.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    status = index_knowledge_chunk(db_session, chunk.id)

    assert status == "failed"
    db_session.refresh(chunk)
    assert chunk.embedding_status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_chunk_index_task.py::test_index_knowledge_chunk_does_not_overwrite_cancelled_failed -v`

Expected: FAIL — `assert status == 'failed'` but got `'ready'`

- [ ] **Step 3: Add helper and guard terminal writes**

在 `backend/src/services/knowledge/chunk_index_task.py` 的 `index_knowledge_chunk` 函数之前追加：

```python
def _finalize_index_status(db: Session, chunk: KnowledgeChunk, status: str) -> str:
    db.refresh(chunk)
    if chunk.embedding_status != "indexing":
        return chunk.embedding_status
    chunk.embedding_status = status
    if status == "ready":
        chunk.indexed_at = datetime.now(timezone.utc)
    db.commit()
    return status
```

将 `index_knowledge_chunk` 内三处直接赋值 + commit 替换为 `_finalize_index_status`：

1. skipped 分支：
```python
return _finalize_index_status(db, chunk, "skipped")
```
（删除原有的 `chunk.embedding_status = "skipped"`、`chunk.indexed_at = ...`、`db.commit()`）

2. embedding 失败分支：
```python
return _finalize_index_status(db, chunk, "failed")
```

3. 成功分支：
```python
return _finalize_index_status(db, chunk, "ready")
```

4. except 分支：
```python
chunk = db.get(KnowledgeChunk, chunk_id)
if chunk is not None:
    return _finalize_index_status(db, chunk, "failed")
return "failed"
```
（删除 rollback 后对 embedding_status 的直接赋值，保留 `logger.exception` 与 rollback）

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_chunk_index_task.py -v`

Expected: PASS（含新增与既有用例）

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_index_task.py backend/tests/unit/test_chunk_index_task.py
git commit -m "fix(knowledge): respect cancelled index status in chunk_index_task"
```

---

### Task 4: 前端 `batchIndexUtils` 工具

**Files:**
- Create: `frontend/src/pages/Knowledge/batchIndexUtils.ts`
- Create: `frontend/src/pages/Knowledge/batchIndexUtils.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/pages/Knowledge/batchIndexUtils.test.ts
import { describe, expect, it, vi } from "vitest";
import { partitionIndexableChunks, runWithConcurrency } from "./batchIndexUtils";

describe("partitionIndexableChunks", () => {
  const items = [
    { id: 1, embedding_status: "pending" },
    { id: 2, embedding_status: "indexing" },
    { id: 3, embedding_status: "ready" },
  ];

  it("splits indexable and indexing ids", () => {
    expect(partitionIndexableChunks(items, [1, 2, 3, 99])).toEqual({
      indexableIds: [1, 3],
      indexingIds: [2],
    });
  });
});

describe("runWithConcurrency", () => {
  it("limits parallel execution", async () => {
    let active = 0;
    let maxActive = 0;
    const ids = [1, 2, 3, 4];

    await runWithConcurrency(ids, async (id) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active -= 1;
      return id;
    }, 2);

    expect(maxActive).toBeLessThanOrEqual(2);
  });

  it("collects errors without stopping early", async () => {
    const results = await runWithConcurrency([1, 2], async (id) => {
      if (id === 1) throw new Error("boom");
      return id;
    }, 2);

    expect(results).toEqual([
      { id: 1, error: expect.any(Error) },
      { id: 2, value: 2 },
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- batchIndexUtils.test.ts`

Expected: FAIL — module not found

- [ ] **Step 3: Implement utils**

```typescript
// frontend/src/pages/Knowledge/batchIndexUtils.ts
export interface ChunkEmbeddingRow {
  id: number;
  embedding_status?: string | null;
}

export interface PartitionResult {
  indexableIds: number[];
  indexingIds: number[];
}

export function partitionIndexableChunks(
  items: ChunkEmbeddingRow[],
  selectedIds: number[],
): PartitionResult {
  const byId = new Map(items.map((item) => [item.id, item]));
  const indexableIds: number[] = [];
  const indexingIds: number[] = [];

  for (const id of selectedIds) {
    const row = byId.get(id);
    if (!row) continue;
    if (row.embedding_status === "indexing") {
      indexingIds.push(id);
    } else {
      indexableIds.push(id);
    }
  }
  return { indexableIds, indexingIds };
}

export type ConcurrencyResult<T> =
  | { id: number; value: T }
  | { id: number; error: Error };

export async function runWithConcurrency<T>(
  ids: number[],
  fn: (id: number) => Promise<T>,
  limit: number,
): Promise<ConcurrencyResult<T>[]> {
  const results: ConcurrencyResult<T>[] = [];
  let cursor = 0;

  async function worker() {
    while (cursor < ids.length) {
      const current = cursor;
      cursor += 1;
      const id = ids[current];
      try {
        const value = await fn(id);
        results.push({ id, value });
      } catch (error) {
        results.push({ id, error: error as Error });
      }
    }
  }

  const workers = Array.from({ length: Math.min(limit, ids.length) }, () => worker());
  await Promise.all(workers);
  return results.sort((a, b) => a.id - b.id);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- batchIndexUtils.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Knowledge/batchIndexUtils.ts frontend/src/pages/Knowledge/batchIndexUtils.test.ts
git commit -m "feat(frontend): add batchIndexUtils for browse page batch index"
```

---

### Task 5: 前端 API 客户端

**Files:**
- Modify: `frontend/src/services/knowledgeChunks.ts`

- [ ] **Step 1: Export terminal statuses and add markChunksIndexFailed**

在 `frontend/src/services/knowledgeChunks.ts` 将：

```typescript
const TERMINAL_EMBEDDING_STATUSES = new Set(["ready", "failed", "skipped"]);
```

改为：

```typescript
export const TERMINAL_EMBEDDING_STATUSES = new Set(["ready", "failed", "skipped"]);
```

在 `indexKnowledgeChunk` 函数之后追加：

```typescript
export async function markChunksIndexFailed(
  kbId: string,
  chunkIds: number[],
): Promise<{ updated_ids: number[]; skipped_ids: number[] }> {
  return apiRequest<{ updated_ids: number[]; skipped_ids: number[] }>(
    `/api/v1/kbs/${kbId}/knowledge-chunks/mark-index-failed`,
    {
      method: "POST",
      body: { chunk_ids: chunkIds },
    },
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build`

Expected: build succeeds（或至少无 knowledgeChunks 相关类型错误）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/knowledgeChunks.ts
git commit -m "feat(frontend): add markChunksIndexFailed API client"
```

---

### Task 6: `KnowledgeBrowsePage` 多选与批量状态机

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx`

- [ ] **Step 1: Add imports and state**

在现有 `antd` import 行合并追加 `Progress`、`Typography`，并从 `react` 引入 `Key`：

```typescript
import { ..., Progress, Typography } from "antd";
import type { Key } from "react";
import {
  getKnowledgeChunk,
  markChunksIndexFailed,
  TERMINAL_EMBEDDING_STATUSES,
} from "../../services/knowledgeChunks";
import {
  partitionIndexableChunks,
  runWithConcurrency,
} from "./batchIndexUtils";

const { Text } = Typography;
const BATCH_INDEX_CONCURRENCY = 3;
const BATCH_INDEX_POLL_MS = 3000;
const BATCH_INDEX_TIMEOUT_MS = 30 * 60 * 1000;

interface BatchIndexState {
  active: boolean;
  submittedIds: number[];
  skippedIds: number[];
  terminalIds: number[];
  failedIds: number[];
  cancelRequested: boolean;
  submitFailedIds: number[];
}
```

在组件 state 区（`indexingId` 附近）追加：

```typescript
const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([]);
const [batchIndex, setBatchIndex] = useState<BatchIndexState | null>(null);
const [showBatchProgress, setShowBatchProgress] = useState(false);
```

- [ ] **Step 2: Add helper to read current table rows**

在组件内、`refreshList` 之后追加：

```typescript
const currentRows = useMemo(
  () => (semanticMode ? searchItems : items),
  [items, searchItems, semanticMode],
);

const titleById = useMemo(
  () => new Map(currentRows.map((row) => [row.id, row.title || `ID ${row.id}`])),
  [currentRows],
);
```

- [ ] **Step 3: Add status refresh helper**

```typescript
const applyEmbeddingStatuses = useCallback(
  (statusById: Map<number, string>) => {
    if (semanticMode) {
      setSearchItems((prev) =>
        prev.map((item) => {
          const next = statusById.get(item.id);
          return next ? { ...item, embedding_status: next } : item;
        }),
      );
    } else {
      setItems((prev) =>
        prev.map((item) => {
          const next = statusById.get(item.id);
          return next ? { ...item, embedding_status: next } : item;
        }),
      );
    }
  },
  [semanticMode],
);

const fetchStatusesForIds = useCallback(
  async (ids: number[]) => {
    if (!selectedKbId || ids.length === 0) return new Map<number, string>();
    const pairs = await Promise.all(
      ids.map(async (id) => {
        const detail = await getKnowledgeChunk(selectedKbId, id);
        return [id, detail?.embedding_status ?? "failed"] as const;
      }),
    );
    return new Map(pairs);
  },
  [selectedKbId],
);
```

- [ ] **Step 4: Implement finalizeBatchIndex**

```typescript
const finalizeBatchIndex = useCallback(
  (state: BatchIndexState, cancelled: boolean) => {
    const failedCount = state.failedIds.length + state.submitFailedIds.length;
    const successCount = state.terminalIds.filter((id) => !state.failedIds.includes(id)).length;

    if (cancelled) {
      message.info(`已停止批量索引（成功 ${successCount} 条，失败 ${failedCount} 条）`);
    } else if (failedCount === 0) {
      message.success(`批量索引完成，共 ${state.submittedIds.length} 条`);
    } else {
      message.warning(`批量索引完成：成功 ${successCount} 条，失败 ${failedCount} 条`);
      Modal.info({
        title: "批量索引失败明细",
        width: 560,
        content: (
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {[...state.failedIds, ...state.submitFailedIds].map((id) => (
              <li key={id}>{titleById.get(id) ?? `ID ${id}`}</li>
            ))}
          </ul>
        ),
      });
    }

    window.setTimeout(() => {
      setShowBatchProgress(false);
      setBatchIndex(null);
      setSelectedRowKeys([]);
    }, 2000);
  },
  [titleById],
);
```

- [ ] **Step 5: Implement handleBatchIndexCancel**

```typescript
const handleBatchIndexCancel = useCallback(async () => {
  if (!selectedKbId || !batchIndex?.active) return;

  setBatchIndex((prev) => (prev ? { ...prev, cancelRequested: true } : prev));

  const pendingIds = batchIndex.submittedIds.filter(
    (id) => !batchIndex.terminalIds.includes(id),
  );

  if (pendingIds.length > 0) {
    try {
      await markChunksIndexFailed(selectedKbId, pendingIds);
      const statusById = await fetchStatusesForIds(pendingIds);
      applyEmbeddingStatuses(statusById);
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  setBatchIndex((prev) => {
    if (!prev) return prev;
    const mergedFailed = Array.from(new Set([...prev.failedIds, ...pendingIds]));
    const mergedTerminal = Array.from(new Set([...prev.terminalIds, ...pendingIds]));
    finalizeBatchIndex(
      { ...prev, failedIds: mergedFailed, terminalIds: mergedTerminal, active: false },
      true,
    );
    return { ...prev, active: false, failedIds: mergedFailed, terminalIds: mergedTerminal };
  });
}, [
  applyEmbeddingStatuses,
  batchIndex,
  fetchStatusesForIds,
  finalizeBatchIndex,
  selectedKbId,
]);
```

- [ ] **Step 6: Implement handleBatchIndex（主流程）**

```typescript
const handleBatchIndex = useCallback(async () => {
  if (!selectedKbId || batchIndex?.active) return;

  const { indexableIds, indexingIds } = partitionIndexableChunks(
    currentRows,
    selectedRowKeys,
  );

  if (indexingIds.length > 0) {
    message.warning(`已跳过 ${indexingIds.length} 条正在索引中的知识`);
  }
  if (indexableIds.length === 0) {
    message.warning("所选知识均在索引中或无效");
    return;
  }

  setShowBatchProgress(true);
  let cancelRequested = false;
  const initial: BatchIndexState = {
    active: true,
    submittedIds: [],
    skippedIds: indexingIds,
    terminalIds: [],
    failedIds: [],
    cancelRequested: false,
    submitFailedIds: [],
  };
  setBatchIndex(initial);

  const submittedIds: number[] = [];
  const submitFailedIds: number[] = [];
  const skippedIds = [...indexingIds];

  const submitResults = await runWithConcurrency(
    indexableIds,
    async (id) => {
      if (cancelRequested) {
        throw new Error("cancelled");
      }
      await indexKnowledgeChunk(selectedKbId, id);
      submittedIds.push(id);
      applyEmbeddingStatuses(new Map([[id, "indexing"]]));
      return id;
    },
    BATCH_INDEX_CONCURRENCY,
  );

  for (const result of submitResults) {
    if ("error" in result) {
      const msg = result.error.message;
      if (msg.includes("INDEX_IN_PROGRESS") || msg.includes("409")) {
        skippedIds.push(result.id);
      } else if (msg !== "cancelled") {
        submitFailedIds.push(result.id);
      }
    }
  }

  const pollIds = Array.from(new Set(submittedIds));
  if (pollIds.length === 0) {
    finalizeBatchIndex(
      {
        ...initial,
        submittedIds: pollIds,
        skippedIds,
        submitFailedIds,
        active: false,
      },
      cancelRequested,
    );
    setBatchIndex(null);
    return;
  }

  setBatchIndex({
    ...initial,
    submittedIds: pollIds,
    skippedIds,
    submitFailedIds,
  });

  const startedAt = Date.now();
  let terminalIds: number[] = [];
  let failedIds: number[] = [];

  while (terminalIds.length < pollIds.length) {
    setBatchIndex((prev) => {
      if (prev?.cancelRequested) cancelRequested = true;
      return prev;
    });
    if (cancelRequested) break;
    if (Date.now() - startedAt > BATCH_INDEX_TIMEOUT_MS) {
      message.warning("批量索引轮询超时，未完成项将标记为失败");
      const pending = pollIds.filter((id) => !terminalIds.includes(id));
      if (pending.length > 0) {
        await markChunksIndexFailed(selectedKbId, pending);
      }
      break;
    }

    const statusById = await fetchStatusesForIds(
      pollIds.filter((id) => !terminalIds.includes(id)),
    );
    applyEmbeddingStatuses(statusById);

    for (const [id, status] of statusById.entries()) {
      if (TERMINAL_EMBEDDING_STATUSES.has(status)) {
        if (!terminalIds.includes(id)) terminalIds.push(id);
        if (status === "failed" && !failedIds.includes(id)) failedIds.push(id);
      }
    }

    setBatchIndex((prev) =>
      prev
        ? { ...prev, submittedIds: pollIds, terminalIds: [...terminalIds], failedIds: [...failedIds] }
        : prev,
    );

    if (terminalIds.length < pollIds.length) {
      await new Promise((resolve) => setTimeout(resolve, BATCH_INDEX_POLL_MS));
    }
  }

  if (cancelRequested) {
    await handleBatchIndexCancel();
    return;
  }

  finalizeBatchIndex(
    {
      active: false,
      submittedIds: pollIds,
      skippedIds,
      terminalIds,
      failedIds,
      cancelRequested: false,
      submitFailedIds,
    },
    false,
  );
  setBatchIndex(null);
}, [
  applyEmbeddingStatuses,
  batchIndex?.active,
  currentRows,
  fetchStatusesForIds,
  finalizeBatchIndex,
  handleBatchIndexCancel,
  selectedKbId,
  selectedRowKeys,
]);
```

- [ ] **Step 7: Add cleanup on KB change**

```typescript
useEffect(() => {
  return () => {
    if (batchIndex?.active && selectedKbId) {
      void markChunksIndexFailed(
        selectedKbId,
        batchIndex.submittedIds.filter((id) => !batchIndex.terminalIds.includes(id)),
      );
    }
  };
}, [batchIndex, selectedKbId]);
```

切换 `selectedKbId` 时清空选中：

```typescript
useEffect(() => {
  setSelectedRowKeys([]);
  setBatchIndex(null);
  setShowBatchProgress(false);
}, [selectedKbId]);
```

- [ ] **Step 8: Add rowSelection and toolbar UI**

在 `tablePagination` 定义之后追加：

```typescript
const batchRunning = Boolean(batchIndex?.active);
const batchProgressPercent =
  batchIndex && batchIndex.submittedIds.length > 0
    ? Math.round((batchIndex.terminalIds.length / batchIndex.submittedIds.length) * 100)
    : 0;

const rowSelection = {
  selectedRowKeys,
  onChange: (keys: Key[]) => setSelectedRowKeys(keys.map(Number)),
  getCheckboxProps: (record: { id: number; embedding_status?: string }) => ({
    disabled: batchRunning || record.embedding_status === "indexing",
  }),
  preserveSelectedRowKeys: false,
};
```

在表格 `{semanticMode ? (` 之前插入操作栏：

```tsx
<Space style={{ marginBottom: 16 }} wrap>
  <Button
    size="small"
    disabled={batchRunning || currentRows.length === 0}
    onClick={() => setSelectedRowKeys(currentRows.map((row) => row.id))}
  >
    全选当前页
  </Button>
  <Button
    size="small"
    disabled={batchRunning || selectedRowKeys.length === 0}
    onClick={() => setSelectedRowKeys([])}
  >
    取消选择
  </Button>
  {selectedRowKeys.length > 0 ? (
    <Text>已选 {selectedRowKeys.length} 项</Text>
  ) : null}
  <Button
    type="primary"
    size="small"
    disabled={selectedRowKeys.length === 0 || batchRunning}
    onClick={() => void handleBatchIndex()}
  >
    批量构建索引
  </Button>
  {batchRunning ? (
    <Button size="small" danger onClick={() => void handleBatchIndexCancel()}>
      停止
    </Button>
  ) : null}
</Space>
{showBatchProgress && batchIndex ? (
  <div style={{ marginBottom: 16 }}>
    <Progress
      percent={batchProgressPercent}
      format={() => `${batchIndex.terminalIds.length} / ${batchIndex.submittedIds.length}`}
      status={batchRunning ? "active" : batchIndex.failedIds.length ? "exception" : "success"}
    />
  </div>
) : null}
```

两个 `<Table>` 均增加 `rowSelection={rowSelection}`。

- [ ] **Step 9: Manual smoke test**

1. 启动应用，进入知识浏览页
2. 勾选 2 条 `pending` 知识 → 批量构建索引 → 观察进度条与状态 Tag
3. 勾选含 `ready` 的知识 → 确认可重新提交
4. 批量进行中点「停止」→ 未完成变 `failed`
5. 语义搜索模式下重复步骤 2

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx
git commit -m "feat(knowledge): add batch index selection on browse page"
```

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| 当前页多选 + 全选当前页 | Task 6 Step 8 |
| 列表 + 语义搜索双模式 | Task 6（`currentRows` / `semanticMode` 分支） |
| 并发提交、非阻塞 | Task 4 `runWithConcurrency` + Task 6 Step 6 |
| 轮询进度条 | Task 6 Step 6/8 |
| 取消 mark-failed | Task 1–2 backend + Task 5–6 frontend |
| 索引任务不覆盖 cancelled | Task 3 |
| ready 可重建 | 复用现有 index API，Task 6 |
| 只读库允许 | 不绑定 `readOnly` |
| 离开页面 cleanup | Task 6 Step 7 |
| 轮询超时 30min | Task 6 Step 6 |

## Manual Test Checklist（实现后）

- [ ] 列表模式：多选 → 批量索引 → 完成汇总
- [ ] 语义搜索：多选 → 批量索引
- [ ] 中途停止 → `failed`
- [ ] 含 `ready` 重建
- [ ] 只读知识库可批量索引
- [ ] `indexing` 行 checkbox 禁用
