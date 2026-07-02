# Design: 知识录入章节预览 Anchor 切片

**Date**: 2026-07-02  
**Status**: Approved  
**Related**: `entry_content_service.py` · `section_slice.py` · `section_content.py` · `outline_store.py`

## 1. 背景与问题

### 1.1 现状

知识录入页点击目录节点时，调用 `GET .../nodes/{node_id}/preview`，由 `get_node_preview()` 返回章节 Markdown 预览。

当前切片路径：

```text
get_node_preview
  → outline_nodes_from_tree_nodes(DB 节点)   # 无 anchor
  → slice_section_markdown(content_md, nodes, node_id)
  → _build_node_heading_starts（标题 + level 匹配 content.md）
```

### 1.2 问题

| 问题 | 说明 |
|------|------|
| 标题匹配不稳 | TOC 标题（如 `1投标函11`）与 content.md 标题（`# 投标函\t11`）格式不一致 |
| refine 后预览退化 | `tree/refine` 修改 DB 的 `level`/`parent` 后，标题匹配边界变窄，常只剩一行标题 |
| anchor 未使用 | doc-chunk 解析已在 `outline.json` 写入 `anchor.char_start`，预览路径未读取 |
| enrich 路径同样脆弱 | `slice_section_markdown_from_payload` 内部仍走标题匹配，anchor 仅作 fallback |

### 1.3 目标

- 预览与 outline payload 全链路改用 **anchor 定位**，不再用标题关键词搜索定边界
- `tree/refine` 调整层级后，预览仍返回完整章节正文
- 父节点预览包含全部子孙节点正文
- 与目录刷新解耦：不修改 `tree/refine`、不修改 anchor 源数据

### 1.4 不在范围

- 修改 tender_skills / doc-chunk 解析或 `anchor_enricher`
- 修改 `tree/refine` 逻辑
- 前端 UI 改造
- 预览路径使用 content.md 标题搜索或 `titles_compatible` 定边界

## 2. 方案决议

| 议题 | 决议 |
|------|------|
| 范围 | **方案 B**：预览 + `slice_section_markdown_from_payload` / enrich 全链路 anchor 优先 |
| 实现形态 | **方案 2**：新增 `slice_section_by_anchor`，payload 路径全切换；旧标题匹配函数保留但 preview/enrich 不再使用 |
| 数据来源 | 读取已落盘 `outline.json` + `outline_node_map.json`（doc-chunk 解析时写入） |
| tender_skills | 本次不改；仅当实测大量节点缺 `char_start` 时再上游排查 |

## 3. 数据流

```text
用户点击树节点 (DB UUID)
  → load_outline_node_map(doc_id)           # outline_node_id → DB UUID
  → 反查 outline_node_id                    # DB UUID → n1
  → load_outline(doc_id)                    # nodes[].anchor.char_start
  → slice_section_by_anchor(content_md, outline, outline_node_id)
  → content_md[start:end]
  → 查 ChunkAsset / KnowledgeChunk（沿用现有 char range 逻辑）
```

enrich 路径（`section_blocks_for_outline_node`）经 `slice_section_markdown_from_payload` 自动切换到 anchor 切片，调用方签名不变。

```mermaid
flowchart LR
  A[DB node UUID] --> B[outline_node_map 反查]
  B --> C[outline.json anchor]
  C --> D[slice_section_by_anchor]
  D --> E[content_md 片段]
  E --> F[preview 响应]
```

## 4. 切片算法

实现于 `backend/src/services/doc_chunk/section_slice.py`。

### 4.1 节点排序

```text
ordered = nodes sorted by (anchor.char_start ?? ∞, sort_order, node_id)
```

### 4.2 起点

```text
start = node.anchor.char_start
```

若缺失：**不**回退标题搜索。尝试按 `sort_order` 在相邻有 anchor 的节点间推算；仍无法确定则返回 `None`（上层抛 `ContentNotAvailableError`）。

### 4.3 终点（父节点含全部子孙正文）

```text
end = len(content_md)
for other in ordered:
  if other.char_start is None or other.char_start <= start:
    continue
  if other is descendant of node:
    continue
  end = other.char_start
  break
```

**禁止**在 anchor 路径内使用：

- `_build_node_heading_starts`
- `_fallback_char_start` / `titles_compatible`
- `_section_end_by_heading`

### 4.4 前言节点 `__preface__`

```text
end = min(所有有 anchor.char_start 的节点) ；若无则 0
markdown = content_md[0:end]
```

### 4.5 与 DB level 的关系

切片边界**不依赖** DB 树节点的 `level`/`parent`。refine 修改 DB 层级不影响预览范围（范围由 outline anchor + outline 树父子关系决定）。

## 5. 组件改动

| 文件 | 改动 |
|------|------|
| `section_slice.py` | 新增 `slice_section_by_anchor`；`slice_section_markdown_from_payload` 委托给它 |
| `entry_content_service.py` | `get_node_preview` 读 `load_outline` + `load_outline_node_map`，反查 outline_node_id 后 anchor 切片 |
| `section_content.py` | 无签名变更（经 `from_payload` 自动切换） |
| `outline_store.py` | 可选：新增 `resolve_outline_node_id(doc_id, tree_node_id)` 反查工具 |

### 5.1 outline / map 缺失

1. 无 `outline.json` → `ContentNotAvailableError`
2. map 缺条目 → `NodeNotFoundError`
3. 不静默回退到标题匹配

`infer_outline_node_map_from_headings` 仅可用于**建立 map**（与 repair 流程一致），**不得**用于切片定位。

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| 无 `content.md` | `ContentNotAvailableError`（现有） |
| 无 `outline.json` | `ContentNotAvailableError` |
| map 无对应 outline_node_id | `NodeNotFoundError` |
| 节点无 `anchor.char_start` 且无法 sort_order 推算 | `ContentNotAvailableError`（记录 warning 日志） |
| 切片结果为空 | `ContentNotAvailableError`（现有） |

## 7. 契约变更

### 7.1 anchor 优先于标题

原单测 `test_slice_section_ignores_wrong_anchor_char_start` 契约为「标题对、anchor 错时信标题」。新契约为：**信 anchor，不信标题**。该测试需更新断言。

### 7.2 旧函数保留

`slice_section_markdown`（标题匹配路径）保留，供无 outline 的遗留调用（若有）。`get_node_preview` 与 enrich **不得**再调用该路径。

## 8. 测试计划

| 测试 | 内容 |
|------|------|
| `test_slice_section_by_anchor_basic` | 多节点 anchor 正确切片 |
| `test_slice_section_by_anchor_parent_includes_children` | 父节点含子节正文 |
| `test_slice_section_by_anchor_ignores_wrong_level` | outline level 与切片无关时仍正确 |
| 更新 `test_slice_section_ignores_wrong_anchor_char_start` | 断言 anchor 结果 |
| `test_get_node_preview_*` | fixture 补充 outline.json + outline_node_map.json |
| `section_blocks_for_outline_node` 回归 | anchor fixture 下 blocks 正确 |

## 9. 验收标准

1. `tree/refine` 后点击任意目录节点，预览含完整正文（非仅标题行）
2. 父节点预览包含所有子孙节点正文
3. 代码路径中 preview / `from_payload` 无标题关键词边界搜索
4. 单元测试全部通过

## 10. 与 tender_skills 的关系

| 阶段 | 负责方 |
|------|--------|
| 解析写入 `anchor.char_start` | tender_skills `outline/anchor_enricher.py` |
| 落盘 `outline.json` | tender_knowledge `import_service` |
| 预览/enrich 读取 anchor | tender_knowledge（本次实现） |

仅当生产文档大量节点缺少 `anchor.char_start` 时，才需排查 tender_skills 或重新解析文档。
