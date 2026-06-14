# API Contract: Outline Quality（目录质量摘要）

**Feature**: `specs/005-outline-extraction-quality`  
**Version**: 1.1.0（扩展 Epic 3 Actual Bid Parse / Bid Outline API）  
**Base paths**:
- `/api/v1/kbs/{kb_id}/actual-bid-parse`
- `/api/v1/kbs/{kb_id}/bid-outlines`

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

---

## Shared Type: OutlineQualitySummary

```json
{
  "node_count": 120,
  "raw_candidate_count": 300,
  "max_depth": 4,
  "l1_count": 50,
  "l1_ratio": 0.42,
  "needs_manual_review_count": 15,
  "review_ratio": 0.125,
  "extract_strategy": "content_heuristic",
  "warnings": ["high_l1_ratio"],
  "filter_stats": {
    "excluded": 180,
    "kept": 120,
    "by_reason": {
      "body_list_item": 90,
      "date_line": 5,
      "structural_only": 10
    }
  }
}
```

**warnings 枚举（MVP）**:

| Value | 含义 | 前端建议文案 |
|-------|------|-------------|
| `high_l1_ratio` | L1 占比超阈值 | 目录扁平，建议检查层级 |
| `high_review_ratio` | 待复核占比超阈值 | 大量章节需人工复核 |
| `flat_fallback` | 使用扁平降级策略 | 未能识别层级，请手工整理 |
| `empty_outline` | 过滤后无节点 | 未抽取到有效目录 |

---

## GET /actual-bid-parse/tasks

**变更**: `data.items[]` 每项增加可选字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| outline_quality | OutlineQualitySummary \| null | 解析完成且有 suggestion 时填充 |
| file_name | string \| null | 来自 File Import，待办展示用 |
| outline_name | string \| null | 来自 Bid Outline |

**ready 列表过滤（服务端）**:

- `status=ready` 时 MUST 排除 `error_message != null` 的任务
- `status=ready` 时 MUST 要求 `task_phase = full_pipeline`

**Response item 示例**:

```json
{
  "parse_task_id": "uuid",
  "import_id": "uuid",
  "document_id": "uuid",
  "bid_outline_id": "uuid",
  "task_phase": "full_pipeline",
  "status": "ready",
  "file_name": "鼎信餐补标书.docm",
  "outline_name": "鼎信餐补标书.docm",
  "outline_quality": {
    "node_count": 120,
    "l1_ratio": 0.42,
    "warnings": []
  },
  "created_at": "2026-06-14T01:00:00Z"
}
```

---

## GET /actual-bid-parse/tasks/{parse_task_id}

**变更**: `data` 增加：

| 字段 | 类型 | 说明 |
|------|------|------|
| outline_quality | OutlineQualitySummary \| null | 完整摘要 |
| suggestion | object \| null | 现有 suggestion 载荷；含 `outline_quality` 键 |

**Error**: 无变更。

---

## GET /bid-outlines

**变更**: `data.items[]` 每项增加可选字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| outline_quality | OutlineQualitySummary \| null | 该 outline 最近一次成功解析的摘要 |

若同一 `source_doc_id` 无 suggestion，字段为 `null`。

---

## GET /bid-outlines/{bid_outline_id}

**变更**: 详情 `data` 增加 `outline_quality`（同上）。

---

## 非变更端点

以下端点行为不变，仅间接受益于更少噪声节点：

- `GET /bid-outlines/{id}/nodes`
- `POST /actual-bid-parse/tasks/{id}/confirm`
- `POST /actual-bid-parse/trigger`

确认向导仍接收完整 `outline_nodes` 列表（过滤后）；管理员可编辑标题/层级后确认。

---

## 审计与 trace

质量摘要写入 `document_parse_suggestions.payload` 时，解析审计日志 SHOULD 记录：

```json
{
  "action": "outline_quality_computed",
  "detail": {
    "node_count": 120,
    "excluded": 180,
    "warnings": ["high_l1_ratio"]
  }
}
```

`trace_id` 沿用请求头中间件。

---

## 兼容性

- 旧客户端忽略未知字段 `outline_quality`、`file_name` 仍可正常工作。
- 新客户端在字段为 `null` 时展示「质量摘要暂不可用」。
