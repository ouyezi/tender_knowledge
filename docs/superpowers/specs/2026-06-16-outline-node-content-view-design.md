# Design: 目录详情页 — 节点内容查看（Drawer）

**Date**: 2026-06-16  
**Status**: Approved  
**Related**: `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx` · `backend/src/services/section_content_builder.py` · `docs/superpowers/specs/2026-06-14-knowledge-visibility-design.md`

## 1. 背景与目标

### 1.1 现状

目录详情页（`/outlines/:bidOutlineId`）左侧展示可拖拽目录树，右侧为节点属性编辑。用户无法在页面上查看某目录节点对应的源文档正文。

后端已有 `build_section_content()`，可按文档树 heading 节点收集段落/表格/图片并返回 `blocks_v1` JSON。前端已有 `RichContentViewer` 可渲染该格式。`BidOutlineNode.source_node_id` 已关联 `DocumentTreeNode`。

### 1.2 目标

在目录树节点 **悬停** 时出现「查看内容」按钮；点击后在 **右侧 Drawer** 中，将该节点及其 **全部子孙目录** 的正文按目录顺序 **拼接展示**，且 **每个节点展示标题** 作为分隔。

### 1.3 不在范围

- 编辑正文或回写文档树
- 导出 Word/PDF
- 分页/虚拟滚动（首版单请求返回全量子树）
- 非目录详情页（确认向导、模板库等）的同类能力

---

## 2. 用户决策（Brainstorming 确认）

| 维度 | 决议 |
|------|------|
| 正文范围 | **B**：该节点 + 全部子孙目录正文 |
| 展示容器 | **A**：右侧 Drawer |
| 子目录标题 | **A**：每个节点先展示标题，再展示正文 |

---

## 3. 方案对比与决议

| 方案 | 描述 | 决议 |
|------|------|------|
| **① 专用子树 API** | 新增 outline node content 端点，后端子树前序遍历 + `build_section_content` | ✅ **采用** |
| ② 前端 N 次请求 | 前端算子树，逐节点请求文档 API | ❌ 无单节点 API、N+1 |
| ③ 全量预取 | 一次拉取整棵目录所有正文，前端过滤 | ❌ over-fetch |

---

## 4. 交互设计

### 4.1 目录树悬停按钮

- 位置：`OutlineTreeEditor` 每个树节点行右侧
- 触发：`mouseenter` 显示，`mouseleave` 隐藏（仅该行）
- 文案：「查看内容」（`Button type="link" size="small"`）
- 点击：`e.stopPropagation()`，不触发树节点选中；打开内容 Drawer 并加载该节点

### 4.2 内容 Drawer

- 组件：`OutlineNodeContentDrawer`（新建）
- 宽度：720px（与 `OutlineDiffDrawer` 一致）
- 标题：`{节点标题} — 章节内容`
- 副信息：层级 `L{n}`、子节数量（sections 条数）
- 关闭：标准 Drawer `onClose`；再次点击其他节点「查看内容」时复用同一 Drawer，更新内容与 loading
- 加载：打开时请求 API；`Spin` 包裹内容区
- 错误：`Alert` +「重试」按钮

### 4.3 内容区排版

按 `sections` 数组顺序纵向排列，每节结构：

```text
[标题]  ← Typography.Title，level 随 outline level 映射（1→4, 2→5, ≥3 用 strong + 缩进）
[正文]  ← RichContentViewer(kbId, section.content)
[分隔]  ← 节与节之间 24px 间距；可选 Divider（仅当非最后一节）
```

标题左缩进：`(level - 1) * 16px`。

---

## 5. 后端设计

### 5.1 API

```
GET /api/v1/kbs/{kb_id}/bid-outlines/{bid_outline_id}/nodes/{outline_node_id}/content
```

**成功响应（200）：**

```json
{
  "outline_node_id": "uuid",
  "title": "技术方案",
  "bid_outline_id": "uuid",
  "source_doc_id": "uuid",
  "sections": [
    {
      "outline_node_id": "uuid",
      "title": "技术方案",
      "level": 1,
      "sort_order": 0,
      "source_node_id": "uuid-or-null",
      "content": "{\"format\":\"blocks_v1\",\"blocks\":[...]}",
      "has_content": true,
      "empty_reason": null
    }
  ]
}
```

**`empty_reason` 枚举（仅 `has_content=false` 时）：**

| 值 | 含义 |
|----|------|
| `no_source_node` | 目录节点未关联 `source_node_id` |
| `empty_body` | 已关联文档节点但 `blocks` 为空 |

**错误：**

| 状态 | code | 场景 |
|------|------|------|
| 404 | `OUTLINE_NOT_FOUND` | bid_outline 不存在 |
| 404 | `OUTLINE_NODE_NOT_FOUND` | outline_node 不存在或不属于该 outline |
| 404 | `KB_NOT_FOUND` | 已有 kb guard |

### 5.2 服务：`build_outline_subtree_content`

**文件**：`backend/src/services/outline_node_content_service.py`（新建）

**签名：**

```python
def build_outline_subtree_content(
    db: Session,
    *,
    kb_id: UUID,
    bid_outline_id: UUID,
    outline_node_id: UUID,
) -> dict[str, Any]:
    ...
```

**算法：**

1. 查询 `BidOutline`，校验 `kb_id`；取 `source_doc_id`。
2. 查询该 outline 下全部 `BidOutlineNode`。
3. 定位 `outline_node_id`；不存在则抛 `OutlineNodeNotFound`。
4. 构建 `parent_id → children` 映射；DFS/BFS **前序**收集子树节点 ID（含根）。
5. 子树节点按 `(level, sort_order, created_at)` 排序（与列表 API 一致）。
6. 对每个节点：
   - 若 `source_node_id` 非空：调用 `build_section_content(db, document_id=source_doc_id, heading_node_id=source_node_id)`。
   - 否则：`content = blocks_v1([])`，`empty_reason = "no_source_node"`。
   - 解析 JSON，`has_content = len(blocks) > 0`；若 `source_node_id` 有值但 blocks 空：`empty_reason = "empty_body"`。
7. 返回根节点元信息 + `sections` 列表。

**复用**：不修改 `build_section_content` 单节语义（仅该 heading 直属正文块，不含子标题文字）。

### 5.3 路由

在 `backend/src/api/routes/bid_outlines.py` 注册 GET handler，调用上述服务，经 `success()` 信封返回。

---

## 6. 前端设计

### 6.1 API 客户端

**文件**：`frontend/src/services/bidOutlines.ts`

```typescript
export interface OutlineNodeContentSection {
  outline_node_id: string;
  title: string;
  level: number;
  sort_order: number;
  source_node_id: string | null;
  content: string;
  has_content: boolean;
  empty_reason: "no_source_node" | "empty_body" | null;
}

export interface OutlineNodeContentResult {
  outline_node_id: string;
  title: string;
  bid_outline_id: string;
  source_doc_id: string;
  sections: OutlineNodeContentSection[];
}

export async function getOutlineNodeContent(
  kbId: string,
  bidOutlineId: string,
  outlineNodeId: string,
): Promise<OutlineNodeContentResult>;
```

### 6.2 组件变更

| 文件 | 变更 |
|------|------|
| `OutlineTreeEditor.tsx` | 增加 `onViewContent?: (outlineNodeId: string) => void`；`title` 渲染 hover 按钮 |
| `OutlineNodeContentDrawer.tsx` | 新建；请求 API、渲染 sections |
| `OutlineDetailPage.tsx` | 状态 `contentDrawerNodeId`；挂载 Drawer；传 callback 给 TreeEditor |

### 6.3 空态文案

| 条件 | 展示 |
|------|------|
| `no_source_node` | 「暂无关联正文」（标题仍展示） |
| `empty_body` | `RichContentViewer` 默认「暂无正文」 |
| 整棵子树无任何 `has_content` | Drawer 顶部 `Alert type="info"`：「该目录下暂无正文内容」 |

---

## 7. 测试

### 7.1 后端单元测试

**文件**：`backend/tests/unit/test_outline_node_content_service.py`

| 用例 | 断言 |
|------|------|
| 单子节点有正文 | sections 长度 1，`has_content=true` |
| 父子两节点 | sections 前序：父 → 子；各节 content 独立 |
| 无 `source_node_id` | `has_content=false`，`empty_reason=no_source_node` |
| 节点不属于 outline | 404 |
| 空正文块 | `empty_reason=empty_body` |

### 7.2 后端契约测试（可选）

`GET .../content` 返回 200 且 `sections` 为数组。

### 7.3 前端

- `OutlineNodeContentDrawer`：mock API，断言多节标题与 `RichContentViewer` 渲染
- `OutlineTreeEditor`：hover 时按钮可见（可用 `@testing-library/user-event`）

---

## 8. 性能与后续

- 首版：子树节点数通常 < 200，单次请求可接受。
- 若子树过大（>100 节且慢）：后续可加 `section_count` 告警或按需折叠子节（不在本 spec）。

---

## 9. 验收标准

1. 目录详情页悬停任意节点可见「查看内容」。
2. 点击后 Drawer 展示该节点及全部子孙：每节有标题 + 正文。
3. 正文含段落、表格、图片（`blocks_v1` + 现有 media API）。
4. 无关联源节点时仍显示标题与明确空态。
5. 后端单测通过；前端相关测试通过。
