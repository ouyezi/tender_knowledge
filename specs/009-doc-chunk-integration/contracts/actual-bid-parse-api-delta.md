# API Contract Delta: Actual Bid Parse（doc_chunk 集成）

**Base path**: `/api/v1/kbs/{kb_id}/actual-bid-parse`  
**Version**: 1.0.1 (009 增量)  
**Baseline**: [004 actual-bid-parse-api.md](../../004-actual-bid-candidates/contracts/actual-bid-parse-api.md)

## 兼容性声明

**无破坏性变更**。所有端点路径、请求/响应形状与 004 一致。本增量仅扩展任务详情与建议 payload 的可选字段。

---

## GET /tasks/{parse_task_id} — Response 扩展

`data.llm_progress` 可选新增字段：

| Field | Type | When |
|-------|------|------|
| parse_engine | string | `doc_chunk` \| `legacy` |
| doc_chunk_stages | object | parse_engine=doc_chunk |
| outline_node_count | int | 解析完成后 |
| chunk_count | int | 解析完成后 |
| tree_node_count | int | 解析完成后 |

示例：

```json
{
  "parse_task_id": "uuid",
  "status": "ready",
  "task_phase": "full_pipeline",
  "llm_progress": {
    "phase": "full_pipeline",
    "parse_engine": "doc_chunk",
    "doc_chunk_stages": {
      "extract": "success",
      "outline": "success",
      "tree": "success",
      "chunk": "success",
      "enrich": "success"
    },
    "outline_node_count": 173,
    "chunk_count": 175,
    "tree_node_count": 3451,
    "logs": [
      { "ts": "...", "level": "info", "message": "章节分块完成：175 块" }
    ]
  }
}
```

---

## GET /documents/{document_id}/parse-suggestion — Response 扩展

`data` 可选字段：

```json
{
  "doc_chunk": {
    "schema_version": "1.0",
    "manifest_status": "success",
    "outline_strategy": "toc",
    "warnings": []
  }
}
```

---

## POST /trigger — 行为说明（无 schema 变更）

| 条件 | 行为 |
|------|------|
| `USE_DOC_CHUNK_PARSE=true`（默认） | 异步任务使用 doc_chunk 流水线 |
| `USE_DOC_CHUNK_PARSE=false` | 使用 legacy walk_document 流水线 |
| `force_reparse=true` + outline locked | 两种引擎均只生成 structure diff |

错误码不变。doc_chunk 失败时 `status=failed`，`error_message` 含可读原因。

---

## 前端影响

`ActualBidParseConfirmWizard` **无需修改**即可消费既有字段。可选：展示 `parse_engine` 标签（非必须）。
