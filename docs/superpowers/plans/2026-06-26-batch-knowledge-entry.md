# Batch Knowledge Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在知识录入页 `/knowledge/entry` 支持目录树多选批量自动入库（预览 → AI 预填 → `force` 创建），并在来源文档区显示进度条。

**Architecture:** 纯前端改动。将可测试纯函数抽到 `batchIngestUtils.ts`；`KnowledgeEntryPage` 增加多选模式 UI 与串行批量队列，复用现有 `getNodePreview` / `prefillKnowledgeChunk` / `createKnowledgeChunk` API。无后端变更。

**Tech Stack:** React 18, TypeScript, Ant Design 5 (`Tree` checkable, `Progress`), vitest

**Design spec:** `docs/superpowers/specs/2026-06-26-batch-knowledge-entry-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `frontend/src/pages/Knowledge/batchIngestUtils.ts` | 勾选排序、`buildAutoCreatePayload`、`withRetry` |
| `frontend/src/pages/Knowledge/batchIngestUtils.test.ts` | 纯函数单元测试 |
| `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx` | 多选 UI、进度条、批量编排、禁用逻辑 |

> **说明：** 设计稿建议纯函数留在页面内，但 `KnowledgeEntryPage.tsx` 已 897 行；抽到 `batchIngestUtils.ts` 便于单测且控制页面体积。

---

## Task 1: 批量入库纯函数

**Files:**
- Create: `frontend/src/pages/Knowledge/batchIngestUtils.ts`
- Create: `frontend/src/pages/Knowledge/batchIngestUtils.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/pages/Knowledge/batchIngestUtils.test.ts
import { describe, expect, it } from "vitest";
import {
  buildAutoCreatePayload,
  collectCheckedNodeIds,
  withRetry,
} from "./batchIngestUtils";
import type { NodePreview, PrefillResult, TreeNode } from "../../services/knowledgeChunks";

const tree: TreeNode[] = [
  {
    node_id: "a",
    title: "第一章",
    parent_id: null,
    level: 1,
    sort_order: 0,
    ingested: false,
    children: [
      {
        node_id: "b",
        title: "1.1",
        parent_id: "a",
        level: 2,
        sort_order: 0,
        ingested: false,
        children: [],
      },
      {
        node_id: "c",
        title: "1.2",
        parent_id: "a",
        level: 2,
        sort_order: 1,
        ingested: false,
        children: [],
      },
    ],
  },
  {
    node_id: "d",
    title: "第二章",
    parent_id: null,
    level: 1,
    sort_order: 1,
    ingested: false,
    children: [],
  },
];

describe("collectCheckedNodeIds", () => {
  it("returns checked ids in preorder", () => {
    expect(collectCheckedNodeIds(tree, ["c", "a", "d"])).toEqual(["a", "c", "d"]);
  });

  it("ignores unchecked ids", () => {
    expect(collectCheckedNodeIds(tree, ["b"])).toEqual(["b"]);
  });
});

describe("buildAutoCreatePayload", () => {
  const preview: NodePreview = {
    title: "节点标题",
    content_md: "# 正文",
    content_type: "markdown",
    char_start: 10,
    char_end: 20,
    page_start: 1,
    page_end: 2,
    catalog_path: [{ node_id: "b", title: "1.1", level: 2 }],
    assets: [],
  };
  const prefill: PrefillResult = {
    title: "AI 标题",
    summary: "摘要",
    knowledge_type: "technical",
    content_type: "markdown",
    source_type: "bid",
    file_name: "标书.docx",
    quote_mode: "verbatim",
    category: "solution",
    tags: ["tag1"],
    products: [],
    industries: [],
    customer_types: [],
    regions: [],
    status: "draft",
    security_level: "internal",
    review_status: "pending",
    is_template: false,
    winning_flag: true,
  };

  it("maps preview + prefill to create payload with force defaults", () => {
    const payload = buildAutoCreatePayload({
      docId: "doc-1",
      nodeId: "b",
      preview,
      prefill,
      documentName: "标书.docx",
      sourceType: "bid",
    });
    expect(payload).toMatchObject({
      doc_id: "doc-1",
      primary_node_id: "b",
      title: "AI 标题",
      content: "# 正文",
      summary: "摘要",
      catalog_path: preview.catalog_path,
      variables: [],
      exclusion_rules: [],
      need_parent_context: false,
      is_immutable: false,
      retrieval_weight: 1,
      winning_flag: true,
    });
  });

  it("falls back to preview title when prefill title empty", () => {
    const payload = buildAutoCreatePayload({
      docId: "doc-1",
      nodeId: "b",
      preview,
      prefill: { ...prefill, title: "" },
    });
    expect(payload.title).toBe("节点标题");
  });
});

describe("withRetry", () => {
  it("retries once on failure", async () => {
    let calls = 0;
    const result = await withRetry(async () => {
      calls += 1;
      if (calls === 1) throw new Error("fail");
      return "ok";
    });
    expect(result).toBe("ok");
    expect(calls).toBe(2);
  });

  it("throws after second failure", async () => {
    await expect(
      withRetry(async () => {
        throw new Error("always fail");
      }),
    ).rejects.toThrow("always fail");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/pages/Knowledge/batchIngestUtils.test.ts`

Expected: FAIL — module `batchIngestUtils` not found

- [ ] **Step 3: Implement utilities**

```typescript
// frontend/src/pages/Knowledge/batchIngestUtils.ts
import type {
  CreateKnowledgeChunkRequest,
  NodePreview,
  PrefillResult,
  TreeNode,
} from "../../services/knowledgeChunks";

export function collectCheckedNodeIds(nodes: TreeNode[], checkedKeys: React.Key[]): string[] {
  const checkedSet = new Set(checkedKeys.map(String));
  const result: string[] = [];

  function walk(ns: TreeNode[]) {
    for (const node of ns) {
      if (checkedSet.has(node.node_id)) {
        result.push(node.node_id);
      }
      if (node.children?.length) {
        walk(node.children);
      }
    }
  }

  walk(nodes);
  return result;
}

export function buildAutoCreatePayload(params: {
  docId: string;
  nodeId: string;
  preview: NodePreview;
  prefill: PrefillResult;
  documentName?: string;
  sourceType?: string;
}): CreateKnowledgeChunkRequest {
  const { docId, nodeId, preview, prefill, documentName, sourceType } = params;

  return {
    doc_id: docId,
    primary_node_id: nodeId,
    title: prefill.title || preview.title || "",
    content: preview.content_md,
    summary: prefill.summary ?? null,
    knowledge_type: prefill.knowledge_type,
    content_type: prefill.content_type || preview.content_type,
    source_type: prefill.source_type ?? sourceType,
    file_name: prefill.file_name || documentName || null,
    project_name: prefill.project_name ?? null,
    page_start: preview.page_start ?? null,
    page_end: preview.page_end ?? null,
    char_start: preview.char_start ?? null,
    char_end: preview.char_end ?? null,
    catalog_path: preview.catalog_path,
    parent_id: null,
    need_parent_context: false,
    quote_mode: prefill.quote_mode,
    category: prefill.category,
    tags: prefill.tags ?? [],
    products: prefill.products ?? [],
    industries: prefill.industries ?? [],
    customer_types: prefill.customer_types ?? [],
    regions: prefill.regions ?? [],
    issue_date: prefill.issue_date ?? null,
    expire_date: prefill.expire_date ?? null,
    status: prefill.status,
    is_template: Boolean(prefill.is_template),
    template_type: prefill.template_type ?? null,
    variables: [],
    is_immutable: false,
    exclusion_rules: [],
    retrieval_weight: 1,
    security_level: prefill.security_level,
    owner: null,
    review_status: prefill.review_status,
    winning_flag: Boolean(prefill.winning_flag),
    edit_distance_avg: null,
  };
}

export async function withRetry<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (firstError) {
    try {
      return await fn();
    } catch {
      throw firstError;
    }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/pages/Knowledge/batchIngestUtils.test.ts`

Expected: PASS (3 suites)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Knowledge/batchIngestUtils.ts frontend/src/pages/Knowledge/batchIngestUtils.test.ts
git commit -m "feat(entry): add batch ingest utility helpers with tests"
```

---

## Task 2: 多选模式 UI（目录树 + 底部栏）

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx`

- [ ] **Step 1: Add imports and state**

在文件顶部增加：

```typescript
import { Progress } from "antd";  // 合并到现有 antd import
import { collectCheckedNodeIds } from "./batchIngestUtils";
```

在组件 state 区增加：

```typescript
type BatchIngestState = {
  active: boolean;
  total: number;
  completed: number;
  currentNodeId?: string;
  cancelRequested: boolean;
  failedItems: Array<{ nodeId: string; title: string; error: string }>;
};

const [selectionMode, setSelectionMode] = useState(false);
const [checkedKeys, setCheckedKeys] = useState<React.Key[]>([]);
const [batchIngest, setBatchIngest] = useState<BatchIngestState | null>(null);
const [showProgressBar, setShowProgressBar] = useState(false);
```

增加派生值：

```typescript
const batchRunning = Boolean(batchIngest?.active);
const checkedCount = checkedKeys.length;
const progressPercent =
  batchIngest && batchIngest.total > 0
    ? Math.round((batchIngest.completed / batchIngest.total) * 100)
    : 0;
```

- [ ] **Step 2: Extend `toTreeData` for current-node highlight**

```typescript
function toTreeData(
  nodes: TreeNode[],
  options?: { currentNodeId?: string },
): DataNode[] {
  return nodes.map((node) => ({
    key: node.node_id,
    title: (
      <Space size={8}>
        <span style={options?.currentNodeId === node.node_id ? { fontWeight: 600, color: "#1677ff" } : undefined}>
          {node.title || "(未命名节点)"}
        </span>
        {node.ingested ? <Tag color="green">已入库</Tag> : null}
        {node.has_blueprint ? <Tag color="blue">已生成蓝图</Tag> : null}
      </Space>
    ),
    children: toTreeData(node.children ?? [], options),
  }));
}
```

- [ ] **Step 3: Replace tree panel Card**

将 `treePanel` 的 `Card` 改为带 `extra` 与 flex body：

```tsx
treePanel={
  <Card
    title="目录树"
    style={WORKSPACE_CARD_STYLE}
    styles={{ body: { ...WORKSPACE_CARD_BODY_STYLE, display: "flex", flexDirection: "column", padding: 0 } }}
    extra={
      !readOnly ? (
        <Button
          size="small"
          disabled={loadingTree || treeNodes.length === 0 || batchRunning}
          onClick={() => {
            setSelectionMode(true);
            setCheckedKeys([]);
          }}
        >
          选择
        </Button>
      ) : null
    }
  >
    <div style={{ flex: 1, overflow: "auto", padding: "0 24px", minHeight: 0 }}>
      {loadingTree ? (
        <Spin />
      ) : treeNodes.length === 0 ? (
        <Text type="secondary">当前文档暂无目录结构</Text>
      ) : (
        <Tree
          checkable={selectionMode}
          checkedKeys={checkedKeys}
          onCheck={(keys) => {
            const next = Array.isArray(keys) ? keys : keys.checked;
            setCheckedKeys(next);
          }}
          disabled={batchRunning}
          treeData={toTreeData(treeNodes, { currentNodeId: batchIngest?.currentNodeId })}
          selectedKeys={selectedNodeId ? [selectedNodeId] : []}
          onSelect={(keys) => {
            if (batchRunning) return;
            setSelectedNodeId(keys[0] as string | undefined);
          }}
        />
      )}
    </div>
    {selectionMode ? (
      <div
        style={{
          borderTop: "1px solid #f0f0f0",
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexShrink: 0,
        }}
      >
        <Text>已选 {checkedCount} 项</Text>
        <Button
          type="primary"
          size="small"
          disabled={checkedCount === 0 || batchRunning}
          onClick={() => void handleBatchIngest()}
        >
          添加到知识库
        </Button>
        <Button
          size="small"
          disabled={batchRunning}
          onClick={() => {
            setSelectionMode(false);
            setCheckedKeys([]);
          }}
        >
          取消选择
        </Button>
        {batchRunning ? (
          <Button size="small" danger onClick={() => setBatchIngest((prev) => (prev ? { ...prev, cancelRequested: true } : prev))}>
            停止
          </Button>
        ) : null}
      </div>
    ) : null}
  </Card>
}
```

> `handleBatchIngest` 在 Task 3 实现；此步可先写空函数 `const handleBatchIngest = useCallback(async () => {}, []);` 保证编译通过。

- [ ] **Step 4: Disable single-entry button in selection mode**

章节预览 Card `extra` 中「添加到知识库」按钮：

```tsx
<Button
  disabled={!preview || readOnly || selectionMode || batchRunning}
  onClick={() => void handlePrefill()}
>
  添加到知识库
</Button>
```

- [ ] **Step 5: Disable document Select during batch**

```tsx
<Select
  ...
  disabled={selectionMode || batchRunning}
  ...
/>
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && npm run build`

Expected: PASS (TypeScript compile OK)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx
git commit -m "feat(entry): add directory tree multi-select UI shell"
```

---

## Task 3: 进度条与批量编排逻辑

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx`

- [ ] **Step 1: Add progress bar below document Select**

在来源文档 `Select` 下方（同一 `flexShrink: 0` 容器内）：

```tsx
{showProgressBar && batchIngest ? (
  <div style={{ width: "100%" }}>
    <Progress
      percent={progressPercent}
      format={() => `${batchIngest.completed} / ${batchIngest.total}`}
      status={batchRunning ? "active" : batchIngest.failedItems.length ? "exception" : "success"}
    />
  </div>
) : null}
```

- [ ] **Step 2: Implement `handleBatchIngest`**

```typescript
const handleBatchIngest = useCallback(async () => {
  if (!selectedKbId || !selectedDocId || readOnly) return;

  const nodeIds = collectCheckedNodeIds(treeNodes, checkedKeys);
  if (nodeIds.length === 0) {
    message.warning("请先勾选目录节点");
    return;
  }

  setShowProgressBar(true);
  setBatchIngest({
    active: true,
    total: nodeIds.length,
    completed: 0,
    cancelRequested: false,
    failedItems: [],
  });

  let successCount = 0;
  const failedItems: BatchIngestState["failedItems"] = [];
  let stopped = false;

  for (const nodeId of nodeIds) {
    setBatchIngest((prev) =>
      prev ? { ...prev, currentNodeId: nodeId } : prev,
    );

    const nodeTitle = findTreeNodeById(treeNodes, nodeId)?.title ?? nodeId;

    try {
      await withRetry(async () => {
        const nodePreview = await getNodePreview(selectedKbId, selectedDocId, nodeId);
        const prefill = await prefillKnowledgeChunk(selectedKbId, {
          doc_id: selectedDocId,
          primary_node_id: nodeId,
          content: nodePreview.content_md,
          metadata: {
            source_type: selectedDocument?.source_type ?? "bid",
            file_name: selectedDocument?.document_name,
          },
        });
        const payload = buildAutoCreatePayload({
          docId: selectedDocId,
          nodeId,
          preview: nodePreview,
          prefill,
          documentName: selectedDocument?.document_name,
          sourceType: selectedDocument?.source_type,
        });
        await createKnowledgeChunk(selectedKbId, payload, true);
      });
      successCount += 1;
      setTreeNodes((prev) => markNodeIngested(prev, nodeId));
    } catch (error) {
      failedItems.push({
        nodeId,
        title: nodeTitle,
        error: (error as Error).message,
      });
    }

    setBatchIngest((prev) =>
      prev
        ? {
            ...prev,
            completed: prev.completed + 1,
            failedItems: [...failedItems],
          }
        : prev,
    );

    if (batchIngest?.cancelRequested) {
      // use functional read below instead — see note
    }
  }

  // IMPORTANT: use a local `let cancelRequested = false` updated via ref or check state inside loop:
}, [...]);
```

**修正：** 循环内用局部变量跟踪取消，避免闭包读旧 state：

```typescript
let cancelRequested = false;
// 停止按钮: setBatchIngest(prev => { cancelRequested = true; return prev ? { ...prev, cancelRequested: true } : prev; })

for (const nodeId of nodeIds) {
  if (cancelRequested) {
    stopped = true;
    break;
  }
  // ... process node ...
  setBatchIngest((prev) => {
    if (prev?.cancelRequested) cancelRequested = true;
    return prev
      ? { ...prev, completed: prev.completed + 1, currentNodeId: nodeId, failedItems: [...failedItems] }
      : prev;
  });
  if (cancelRequested) {
    stopped = true;
    break;
  }
}

setBatchIngest((prev) => (prev ? { ...prev, active: false, currentNodeId: undefined } : prev));

if (stopped) {
  const remaining = nodeIds.length - (successCount + failedItems.length);
  message.info(`已停止，剩余 ${remaining} 项未处理（成功 ${successCount} 条）`);
} else if (failedItems.length === 0) {
  message.success(`已成功添加 ${successCount} 条知识`);
} else {
  message.warning(`成功 ${successCount} 条，失败 ${failedItems.length} 条`);
  Modal.info({
    title: "批量入库失败明细",
    width: 560,
    content: (
      <ul style={{ paddingLeft: 20, margin: 0 }}>
        {failedItems.map((item) => (
          <li key={item.nodeId}>
            {item.title}: {item.error}
          </li>
        ))}
      </ul>
    ),
  });
}

window.setTimeout(() => setShowProgressBar(false), 2000);
```

补充 import：

```typescript
import { buildAutoCreatePayload, collectCheckedNodeIds, withRetry } from "./batchIngestUtils";
```

- [ ] **Step 3: Wire stop button to set cancel flag**

停止按钮 `onClick`：

```typescript
onClick={() =>
  setBatchIngest((prev) => (prev ? { ...prev, cancelRequested: true } : prev))
}
```

循环开头检查 `batchIngest` 的 functional update 读 `cancelRequested`（见 Step 2 修正）。

- [ ] **Step 4: Exit selection mode after batch completes**

批量结束后（`setBatchIngest` active=false 之后）：

```typescript
setSelectionMode(false);
setCheckedKeys([]);
```

- [ ] **Step 5: Run tests and build**

Run:
```bash
cd frontend && npm test -- src/pages/Knowledge/batchIngestUtils.test.ts
cd frontend && npm run build
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx
git commit -m "feat(entry): batch auto-ingest with progress bar and retry"
```

---

## Task 4: 手动验收

**Files:** none (verification only)

- [ ] **Step 1: Start dev server**

Run: `cd frontend && npm run dev`

Open: `http://localhost:5173/knowledge/entry`（需已登录并选择知识库）

- [ ] **Step 2: Run acceptance checklist**

| # | 操作 | 期望 |
|---|------|------|
| 1 | 点「选择」 | 复选框出现，底部栏显示 |
| 2 | 勾选父节点 + 子节点 | 「已选 N 项」计数正确 |
| 3 | 点底部「添加到知识库」 | 进度条 `0/N` 开始，逐条递增 |
| 4 | 完成后 | 节点绿标「已入库」，Toast 成功数 |
| 5 | 对已入库节点再批量 | 无确认弹窗，自动覆盖 |
| 6 | 批量中点「停止」 | 当前条完成后停止，Toast 含剩余数 |
| 7 | 点「取消选择」 | 退出多选，单条「添加到知识库」恢复 |
| 8 | `readOnly` 知识库 | 无「选择」按钮 |

- [ ] **Step 3: Final commit if any fixups**

```bash
git add -A
git commit -m "fix(entry): address batch ingest acceptance feedback"
```

（仅在有修复时提交）

---

## Self-Review (plan vs spec)

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 「选择」按钮 + 复选框 | Task 2 Step 3 |
| 底部固定栏（已选/添加/取消/停止） | Task 2 Step 3 |
| 来源文档下进度条 | Task 3 Step 1 |
| 全自动 preview→prefill→create(force) | Task 3 Step 2 |
| 任意节点可选 | Task 1 `collectCheckedNodeIds` + Task 2 checkable |
| 失败重试 1 次后跳过 + 汇总 | Task 1 `withRetry` + Task 3 Modal |
| 批量中 UI 锁定 | Task 2 Step 4–5, Task 3 |
| readOnly 隐藏选择 | Task 2 Step 3 |
| 无后端改动 | 全计划 |

无 TBD / 占位符。类型与 `knowledgeChunks.ts` 接口一致。
