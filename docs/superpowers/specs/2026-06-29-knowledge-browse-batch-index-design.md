# 知识浏览页批量构建索引 — 设计说明

**日期：** 2026-06-29  
**状态：** 已评审待实现

## 背景与目标

知识浏览页（`KnowledgeBrowsePage`）当前仅支持单行「构建索引 / 重新索引」。用户需要多选知识块并批量触发索引，同时支持「全选当前页」快捷操作。索引执行采用非阻塞提交 + 轻量进度轮询；用户取消或异常时，未完成项应落为 `failed` 状态。

## 需求摘要

| 维度 | 决策 |
|------|------|
| 选择范围 | 当前页可见记录（列表分页页 / 语义搜索 top-K） |
| 按筛选批量 | 「全选当前页」，不跨分页 |
| 执行模式 | 并发提交 index API，底部进度条轮询 `embedding_status` |
| 取消/中断 | 调用 mark-failed API，将仍为 `indexing` 的标为 `failed` |
| 视图支持 | 列表模式 + 语义搜索模式 |
| 重建策略 | 选中即提交（含 `ready`）；仅 `indexing` 跳过并提示 |
| 只读库 | 允许批量索引（与单行行为一致） |

## 方案选型

采用 **前端编排 + 复用单条 Index API**，辅以最小后端增补：

- 前端：`rowSelection`、并发 POST、`batchIndex` 状态机、轮询刷新
- 后端：新增 `mark-index-failed` 批量接口；`index_knowledge_chunk` 增加取消防护

不引入 Batch Job 表/队列（当前页规模 ≤ `page_size`，默认 20，足够）。

## UI / 交互

### 操作栏

在表格上方（筛选区/语义搜索栏之下）增加批量操作区：

- **全选当前页**：选中当前 `dataSource` 全部行
- **取消选择**：清空 `selectedRowKeys`
- 有选中时显示：`已选 N 项` | **批量构建索引** | 进行中显示 **停止**

### 表格

- Ant Design `rowSelection` 多选列
- `embedding_status === 'indexing'` 的行：checkbox 禁用
- 提交时跳过 `indexing` 项，`message.warning` 提示跳过数量

### 进度

- 表格下方 `Progress`：`已完成 M / 总计 T`（T = 本轮实际提交数）
- 轮询间隔约 3s，局部更新行 `embedding_status`
- 全部终态后：toast 汇总；有 `failed` 时 Modal 列出标题 + 状态
- 2s 后隐藏进度条并清空选中

### 只读模式

与单行「构建索引」一致：不禁用多选与批量索引。

## 前端状态机

### 状态结构

```typescript
interface BatchIndexState {
  active: boolean;
  submittedIds: number[];
  skippedIds: number[];
  terminalIds: number[];
  failedIds: number[];
  cancelRequested: boolean;
  submitError?: string;
}
```

独立维护 `selectedRowKeys: number[]`。

### 生命周期

1. **Idle** → 用户点击「批量构建索引」
2. **Submitting** → 并发调用 `indexKnowledgeChunk`（concurrency = 3）
3. **Polling** → 每 3s 刷新当前视图 `embedding_status`
4. **Cancelling**（可选）→ `markChunksIndexFailed` → **Done**
5. **Done** → 汇总提示 → 2s 后回 Idle

### 提交流程

1. `partitionIndexableChunks` 过滤 `indexing`
2. 可提交数为 0 → warning 返回
3. 并发 POST；单条失败继续其余；409 记入 `skippedIds`
4. POST 阶段结束即进入 Polling，不等待单条完成

### 取消流程

1. `cancelRequested = true`，提交阶段停止新发 POST
2. `pendingIds = submittedIds - terminalIds`
3. 调用 `markChunksIndexFailed(kbId, pendingIds)`
4. 刷新列表，展示汇总

### 语义搜索模式

- `dataSource` 为 `searchItems`
- 轮询时对 `submittedIds` 调用 `getKnowledgeChunk` 或刷新 search 结果
- 选择与工具栏逻辑与列表模式共用 handler

### 工具模块

新增 `frontend/src/pages/Knowledge/batchIndexUtils.ts`：

- `partitionIndexableChunks(items, selectedIds)`
- `runWithConcurrency(ids, fn, limit)`
- 复用 `TERMINAL_EMBEDDING_STATUSES`（`knowledgeChunks.ts`）

### 页面卸载 / 切换知识库

`useEffect` cleanup：若 `batchIndex.active`，触发 cancel 流程（mark-failed pending）。

## 后端

### 新增 API

```
POST /api/v1/kbs/{kb_id}/knowledge-chunks/mark-index-failed
```

**Request:**

```json
{ "chunk_ids": [1, 2, 3] }
```

**行为：**

- 仅更新属于该 `kb_id` 且 `embedding_status = 'indexing'` 的记录 → `failed`
- 不修改 `indexed_at`
- 返回 `{ "updated_ids": [...], "skipped_ids": [...] }`

**Schema:** `MarkChunksIndexFailedRequest`（`chunk_ids: list[int]`，Field max_length=200）

**路由顺序：** 静态路径 `mark-index-failed` 注册在 `/{chunk_id}/index` 之前。

### 现有 Index API

`POST /{chunk_id}/index` 契约不变。`force` 字段当前未使用；`ready` 状态可直接重新提交（仅 `indexing` 返回 409）。

### 索引任务取消防护

在 `index_knowledge_chunk` 写入终态（`ready` / `failed` / `skipped`）前：

```python
db.refresh(chunk)
if chunk.embedding_status != "indexing":
    return chunk.embedding_status
```

覆盖：skipped、embedding 失败、成功 ready、except 分支 failed。

防止用户取消后，仍在执行的后台任务将 `failed` 覆盖为 `ready`。

### 服务层

`mark_chunks_index_failed(db, kb_id, chunk_ids) -> MarkIndexFailedResult`  
置于 `chunk_service.py` 或同级小模块，路由薄封装。

## 错误处理

| 场景 | 处理 |
|------|------|
| 全部为 `indexing` | 提交前拦截 warning |
| 单条 POST 失败 | 记入失败列表，继续；轮询前或取消时 mark-failed |
| POST 409 | 记入 `skippedIds` |
| 用户「停止」 | 停发 POST + mark-failed pending |
| 轮询超时（30min） | mark-failed 未终态项 + warning |
| 索引任务异常 | 后台标 `failed`，轮询收敛 |
| 离开页面 / 切换 KB | cleanup 触发 cancel |

## 测试

### 后端单元

- `mark_chunks_index_failed`：kb 隔离、仅 indexing 更新、skipped 正确
- `index_knowledge_chunk`：cancel 后完成不覆盖 ready

### 前端单元

- `batchIndexUtils.test.ts`：`partitionIndexableChunks`、`runWithConcurrency`

### 集成（可选）

- `POST mark-index-failed` API 契约

### 手工

- 列表：多选 → 批量索引 → 进度 → 汇总
- 语义搜索：同上
- 中途停止 → 未完成变 `failed`
- 含 `ready` 重建
- 只读库可批量索引

## 不在范围内

- 跨分页 / 全库按筛选条件批量索引
- 服务端 Batch Job 队列与 batch_id 追踪
- 批量删除、批量生成技巧等其他批量操作

## 参考实现

- 单条索引：`KnowledgeBrowsePage.handleIndexChunk`、`indexKnowledgeChunk` API
- 批量编排模式：`KnowledgeEntryPage` + `batchIngestUtils.ts`
