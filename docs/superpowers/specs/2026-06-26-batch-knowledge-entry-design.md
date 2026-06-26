# Design: 知识录入页批量自动入库

**Date**: 2026-06-26  
**Status**: Approved (brainstorming)  
**Route**: `/knowledge/entry`  
**Related**: `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md`

---

## 1. 背景与目标

### 1.1 现状

知识录入页（`KnowledgeEntryPage`）当前仅支持**单节点**入库流程：

1. 选择来源文档 → 点击目录树节点
2. 加载章节预览
3. 点击「添加到知识库」→ AI 预填 → 右侧展开表单
4. 用户确认后创建知识条目

目录树节点已有 `ingested`（已入库）标记；后端提供 `getNodePreview`、`prefillKnowledgeChunk`、`createKnowledgeChunk` 三个独立 API，无批量接口。

### 1.2 目标

在目录树支持**多选批量自动入库**，无需展开右侧表单：

- 「目录树」标题旁增加「选择」按钮，进入多选模式后节点显示复选框
- 底部固定栏显示已选数量、「添加到知识库」、「取消选择」
- 「来源文档」下方显示进度条（完成数 / 总数）
- 全自动流水线：预览 → AI 预填 → 直接创建（`force=true`）

### 1.3 用户决策摘要

| 决策点 | 选择 |
|--------|------|
| 批量模式行为 | 全自动流水线，不展开表单 |
| 可选节点范围 | 任意节点（含父节点，内容可能与子节点重叠） |
| 已入库 / 冲突处理 | 全部自动覆盖（`force=true`），无需确认 |
| 操作栏位置 | 目录树底部固定栏 |
| 失败处理 | 每节点重试 1 次，仍失败则跳过，结束后汇总 |

---

## 2. 范围

### 2.1 包含

- `KnowledgeEntryPage.tsx` 多选模式 UI 与批量队列逻辑
- 来源文档区域进度条
- 复用现有 3 个 API，前端串行编排

### 2.2 不包含

- 后端批量 API 或任务队列
- 前端并发 / 限流优化
- 批量模式下的表单预览或逐条人工确认
- 新增自动化测试（手动验收为主）

---

## 3. 方案决议

### 3.1 选定方案：前端串行编排（方案 1）

对每个勾选节点依次调用：

```
getNodePreview → prefillKnowledgeChunk → createKnowledgeChunk(force=true)
```

| 优点 | 缺点 |
|------|------|
| 无后端改动，复用现有逻辑 | 节点多时耗时较长（LLM 串行） |
| 进度条由前端 state 直接驱动 | 刷新页面丢失进行中任务 |
| 与单条录入字段逻辑一致 | |

**未采用**：

- **方案 2（后端批量任务 API）**：开发量大，当前无大批量刚需
- **方案 3（前端并发限流）**：易触发 LLM 限流，错误处理复杂

---

## 4. 交互设计

### 4.1 多选模式入口

- 「目录树」Card 标题右侧增加 **「选择」** 按钮（`readOnly` 时隐藏）
- 点击进入多选模式：
  - 目录树节点显示复选框（Ant Design `Tree` 的 `checkable`）
  - 底部出现固定操作栏
  - 「章节预览」区单条「添加到知识库」禁用

### 4.2 底部固定栏

多选模式下，目录树面板底部固定：

```text
已选 N 项    [添加到知识库]    [取消选择]    [停止*]
* 仅批量进行中显示
```

- **已选 N 项**：实时统计勾选数（含父节点）
- **添加到知识库**：N=0 时禁用；N>0 且未在批量中时可用
- **取消选择**：退出多选模式，清空勾选，恢复普通浏览
- **停止**：批量进行中显示；当前节点处理完后停止，已完成不回滚

### 4.3 进度条

「来源文档」下拉框下方增加 `Progress` 组件：

- 批量进行中：显示 `完成数 / 总数` 及百分比
- 空闲时隐藏
- 完成后短暂显示最终结果（约 2 秒后隐藏）

### 4.4 批量进行中 UI 锁定

- 目录树复选框、底部按钮（除「停止」外）、文档切换均禁用
- 当前处理节点在树中高亮（可选：Processing 图标）
- 右侧表单不自动展开

### 4.5 目录树 Card 布局

Card `body` 改为 flex 列布局：

```text
目录树                    [选择]
├── Tree（flex:1，可滚动）
└── 底部固定栏（多选模式时显示）
```

---

## 5. 批量处理流程

### 5.1 单节点流水线

对每个勾选节点，按**树的前序遍历顺序**处理：

1. `getNodePreview(kbId, docId, nodeId)`
2. `prefillKnowledgeChunk(kbId, { doc_id, primary_node_id, content, metadata })`
3. 组装 `CreateKnowledgeChunkRequest`（preview + prefill 结果，字段与单条 `buildCreatePayload` 对齐）
4. `createKnowledgeChunk(kbId, payload, force=true)`
5. 更新树节点 `ingested=true`；`completedCount++`

### 5.2 重试与失败

- 步骤 1–4 任一步失败 → **自动重试 1 次**
- 仍失败 → 记入 `failedItems: { nodeId, title, error }`，跳过继续下一个
- 全部结束后 Toast 汇总：
  - 全成功：`已成功添加 N 条知识`
  - 部分失败：`成功 X 条，失败 Y 条`（可 Modal 展示失败列表）
  - 用户停止：`已停止，剩余 M 项未处理`

### 5.3 停止行为

- 用户点「停止」→ 设 `cancelRequested=true`
- 当前节点跑完后不再取下一个
- 进度条停在 `已完成 / 总数`

### 5.4 与单条录入的关系

| 模式 | 行为 |
|------|------|
| 普通模式 | 现有流程不变：预览 → 预填 → 表单确认 |
| 多选模式 | 全自动流水线，不展开右侧表单 |
| 批量进行中 | 单条按钮禁用 |

---

## 6. 实现细节

### 6.1 改动文件

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx` | 多选 state、批量队列、进度条、底部栏 |
| `frontend/src/services/knowledgeChunks.ts` | 无改动 |
| 后端 | 无改动 |

### 6.2 新增纯函数（页内抽取，不新建文件）

- **`buildAutoCreatePayload(preview, prefill, docMeta)`** — 从 preview + prefill 组装 `CreateKnowledgeChunkRequest`，不依赖 Form values
- **`collectCheckedNodeIds(tree, checkedKeys)`** — 从 Ant Design Tree 的 checkedKeys 解析待处理 nodeId 列表（前序遍历排序）

### 6.3 状态类型

```typescript
type BatchIngestState = {
  active: boolean;
  total: number;
  completed: number;
  currentNodeId?: string;
  cancelRequested: boolean;
  failedItems: Array<{ nodeId: string; title: string; error: string }>;
};
```

页面级 state 补充：

```typescript
selectionMode: boolean;
checkedKeys: React.Key[];
batchIngest: BatchIngestState | null;
```

### 6.4 目录树改造

```tsx
<Tree
  checkable={selectionMode}
  checkedKeys={checkedKeys}
  onCheck={(keys) => setCheckedKeys(...)}
  selectedKeys={selectedNodeId ? [selectedNodeId] : []}
  onSelect={(keys) => setSelectedNodeId(...)}
  treeData={toTreeData(treeNodes, { currentNodeId: batchIngest?.currentNodeId })}
/>
```

- 勾选与点击选中互不干扰：勾选用于批量，点击用于预览

### 6.5 边界情况

| 场景 | 处理 |
|------|------|
| 切换来源文档 | 多选模式或批量进行中禁止切换 |
| `readOnly` 知识库 | 隐藏「选择」按钮 |
| 空树 / 加载中 | 「选择」按钮禁用 |
| 勾选 0 项 | 「添加到知识库」禁用 |
| 父+子同时勾选 | 按勾选列表各自独立处理 |
| 页面刷新 | 进行中任务丢失（接受，v1 不做持久化） |

---

## 7. 验收标准

1. 点「选择」→ 树节点出现复选框，底部栏出现
2. 勾选多个节点（含父节点）→ 底部显示正确数量
3. 点「添加到知识库」→ 来源文档下进度条 `0/N` 开始递增
4. 完成后节点显示「已入库」绿标，Toast 汇总成功数
5. 对已入库节点再次批量添加 → 自动覆盖，无确认弹窗
6. 模拟失败（如断网）→ 重试 1 次后跳过，最终汇总含失败项
7. 批量中点「停止」→ 当前节点完成后停止，进度条反映实际完成数
8. 点「取消选择」→ 退出多选，复选框消失，单条录入恢复正常

---

## 8. 后续可选增强（本次不做）

- 后端批量任务 API + 进度轮询 / SSE
- 前端并发限流（2–3 路并行 prefill）
- 批量任务断点续传
- 批量前预览勾选列表确认 Modal
