# Data Model: 实际标书解析接入 doc_chunk

**Date**: 2026-06-15  
**Feature**: `specs/009-doc-chunk-integration`

本特性 **不新增数据库表**；扩展既有实体字段与任务元数据。落库对象仍为 Epic 3 域模型。

---

## 1. 运行时上下文（非持久化）

### ImportContext

单次 `doc_chunk` 解析导入的内存映射，生命周期 = `_run_entry` 事务。

| 字段 | 类型 | 说明 |
|------|------|------|
| workspace_path | Path | doc_chunk 工作区根目录 |
| tree_id_map | dict[str, UUID] | doc_chunk `tNNNN` → `DocumentTreeNode.node_id` |
| outline_id_map | dict[str, UUID] | doc_chunk `nNNN` → 用于 BidOutline 构建的临时索引 |
| image_ref_map | dict[str, UUID] | `images/...` → `DocumentMediaAsset.asset_id` |
| chunk_id_map | dict[str, dict] | chunk_id → 已加载 chunk JSON |
| parse_strategy | str | `doc_chunk` \| `legacy` |

---

## 2. 既有实体扩展

### actual_bid_parse_tasks

| 字段 | 变更 | 说明 |
|------|------|------|
| parse_strategy | 已有 enum | 增加语义：`docx` 路径下实际引擎由 `llm_progress.parse_engine` 区分 |
| llm_progress | JSON 扩展 | 新增可选键见下 |

**llm_progress 扩展键**（doc_chunk 路径）：

```json
{
  "parse_engine": "doc_chunk",
  "doc_chunk_stages": {
    "extract": "success",
    "outline": "success",
    "tree": "success",
    "chunk": "success",
    "enrich": "success"
  },
  "workspace_path": "/data/.../doc_chunk_workspaces/{import_id}/{task_id}",
  "outline_node_count": 173,
  "chunk_count": 175,
  "tree_node_count": 3451
}
```

### bid_outlines

| 字段 | 变更 | 说明 |
|------|------|------|
| extract_strategy | enum 扩展 | 新增 `doc_chunk`（或复用 `toc`/`heading_heuristic` 等子策略存于 suggestion） |

**建议**：`extract_strategy` 存粗粒度 `doc_chunk`；细粒度 `outline.json.strategy` 写入 `document_parse_suggestion.outline_quality.strategy`。

### document_parse_suggestions

| 字段 | 变更 | 说明 |
|------|------|------|
| payload | JSON 扩展 | 可选 `doc_chunk: { schema_version, manifest_status, warnings[] }` |

### documents / document_tree_nodes / bid_outline_nodes / candidate_knowledges

**无 schema 变更**。字段语义不变：

- `DocumentTreeNode.content_ref`：图片节点存 `asset_id` UUID 字符串
- `DocumentTreeNode.is_outline_node`：heading 节点 `true`
- `BidOutlineNode.source_node_id`：指向 `DocumentTreeNode` heading
- `CandidateKnowledge.source_node_id`：linkage 主 tree heading
- `CandidateKnowledge.content`：`blocks_v1` JSON 字符串

---

## 3. doc_chunk 工作区 → 实体映射规则

### document_tree.json → DocumentTreeNode

| doc_chunk 字段 | DocumentTreeNode | 规则 |
|----------------|------------------|------|
| node_type | node_type | 直接映射 enum |
| title | title | heading 时 |
| level | level | heading 时 |
| sort_order | sort_order | 直接 |
| text | content_preview | paragraph/table，截断 4000 |
| image_ref | content_ref | 注册 asset 后写 UUID |
| outline_node_id | — | 用于构建 is_outline_node；heading 为 true |
| parent_id | parent_id | 经 tree_id_map 转换 |

### outline.json → BidOutlineNode

通过 `linkage.json` + `TocEntry` 形状适配：

| 来源 | BidOutlineNode |
|------|----------------|
| outline.title | title |
| outline.level | level |
| outline.sort_order | sort_order |
| linkage.document_tree_node_ids[0] | source_node_id（经 tree_id_map） |
| outline.needs_review | 映射 suggestion 质量标记 |

### chunks + linkage → CandidateKnowledge

| 来源 | CandidateKnowledge |
|------|-------------------|
| chunk.title | title |
| blocks（经 blocks_v1） | content |
| linkage primary tree node | source_node_id |
| metadata.suggested_* + rules | suggested_knowledge_type, taxonomy, product_category_ids |
| — | status = pending |
| — | suggestion_source = rule \| hybrid（若用 enrich） |

---

## 4. 状态与事务

### 解析任务状态机

不变：`pending → running → ready | failed`

### 事务边界

doc_chunk 路径单 `_run_entry` 内：

1. `run_pipeline`（文件系统，事务外）
2. `import_service.import_workspace`（单 DB 事务或分阶段 commit 与现 runner 一致）
   - 失败 rollback + 可选保留 workspace
3. downstream entries 标记 completed

与 legacy 相同：Phase 间 `db.commit()` checkpoint 可保留，便于长任务进度查询。

---

## 5. 配置实体（Settings）

见 `research.md` R9。无新表。

---

## 6. 验证规则

| 规则 | 说明 |
|------|------|
| V1 | tree_id_map 无碰撞（每个 doc_chunk node_id 唯一 UUID） |
| V2 | 每个 linkage entry（非 flat_fallback 单节点）有 ≥1 tree heading |
| V3 | 候选 source_node_id 必须存在于当前 document tree |
| V4 | blocks_v1 图片块 asset_id 必须存在于 document_media_assets |
| V5 | Preface chunk 不产生 CandidateKnowledge |
