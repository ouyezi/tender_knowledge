# API Contract: Retrieval Search & Trace

**Base path**: `/api/v1/kbs/{kb_id}/retrieval`  
**Version**: 1.0.0 (Epic 5)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

---

## Common enums

**intent**: `knowledge_lookup` | `material_recommend` | `module_suggestion` | `trace_lookup` | `directory_match`

**object_type**: `ku` | `wiki` | `template` | `template_chapter` | `bid_outline` | `bid_outline_node` | `chapter_pattern` | `manual_asset`

---

## POST /search

统一检索入口（内容检索、素材推荐、目录结构召回）。

**Body**:

```json
{
  "query": "技术方案架构设计",
  "intent": "knowledge_lookup",
  "product_category_ids": ["uuid"],
  "chapter_taxonomy_ids": ["uuid"],
  "knowledge_types": ["solution"],
  "file_purposes": [],
  "object_types": ["ku", "wiki"],
  "tender_requirement_context": {
    "outline_title": "",
    "score_points": ["评分点描述"],
    "rejection_clauses": ["废标条款"]
  },
  "outline_nodes": [
    { "title": "1. 技术方案", "level": 1, "sort_order": 0 }
  ],
  "retrieval_options": {
    "strategy_version_id": "uuid",
    "enable_bm25": true,
    "enable_vector": true,
    "enable_rerank": false,
    "top_k": 20,
    "context_expand_depth": 1
  },
  "return_options": {
    "include_trace": true,
    "include_score_detail": true,
    "include_conflict_flags": true,
    "include_knowledge_pack": true
  }
}
```

**Response `data`**:

```json
{
  "trace_id": "uuid",
  "intent": "knowledge_lookup",
  "strategy_version_id": "uuid",
  "latency_ms": 320,
  "items": [
    {
      "object_type": "ku",
      "object_id": "uuid",
      "title": "云平台架构设计",
      "score": 0.87,
      "score_detail": {
        "bm25": 0.45,
        "vector": 0.32,
        "metadata_boost": 0.1
      },
      "hit_reason": "标题与查询高度匹配，且产品分类一致",
      "source_trace": {
        "import_id": "uuid",
        "source_doc_id": "uuid",
        "source_node_id": "uuid",
        "candidate_id": "uuid"
      },
      "knowledge_pack": {
        "product_category": [{ "category_id": "uuid", "name": "云平台" }],
        "chapter_taxonomy": { "taxonomy_id": "uuid", "name": "技术方案" },
        "template_chapter_hints": [],
        "bid_outline_context": [],
        "chapter_patterns": [],
        "candidate_source": {},
        "import_id": "uuid",
        "score_detail": {},
        "hit_reason": "标题与查询高度匹配，且产品分类一致"
      },
      "conflict_flags": []
    }
  ],
  "directory_match": {
    "match_score": 0.82,
    "coverage_rate": 0.75,
    "score_detail": {
      "product_category": 0.3,
      "chapter_taxonomy": 0.25,
      "title_similarity": 0.18,
      "level_order": 0.08,
      "knowledge_coverage": 0.05
    },
    "matched_outline_ids": ["uuid"],
    "matched_template_chapter_ids": ["uuid"],
    "matched_pattern_ids": ["uuid"],
    "missing_chapters": [
      {
        "pattern_id": "uuid",
        "pattern_name": "售后服务",
        "frequency": 5,
        "reason": "产品分类下高频章节未覆盖"
      }
    ]
  },
  "total": 12
}
```

**Errors**:

| Code | HTTP | When |
|------|------|------|
| INVALID_INTENT | 422 | intent 不在枚举内 |
| STRATEGY_VERSION_NOT_FOUND | 404 | 指定策略版本不存在 |
| RETRIEVAL_FAILED | 500 | 管线失败；partial trace 可能已写入 |

---

## POST /directory-match

目录级专用匹配（Bid Outline / Template Chapter / Chapter Pattern），等价于
`intent=directory_match` 的 search 快捷端点。

**Body**:

```json
{
  "product_category_ids": ["uuid"],
  "outline_nodes": [
    { "title": "1. 技术方案", "level": 1 },
    { "title": "1.1 总体架构", "level": 2 }
  ],
  "tender_requirement_context": {
    "score_points": [],
    "rejection_clauses": []
  },
  "retrieval_options": { "top_k": 10 },
  "return_options": { "include_trace": true, "include_score_detail": true }
}
```

**Response `data`**: `directory_match` 对象（同上）+ `trace_id`。

---

## GET /traces

检索日志列表（检索优化中心）。

**Query**: `intent`, `status`, `from`, `to`, `operator_id`, `page`, `page_size`

**Response `data.items[]`**:

```json
{
  "trace_id": "uuid",
  "intent": "knowledge_lookup",
  "strategy_version_id": "uuid",
  "status": "success",
  "latency_ms": 320,
  "result_count": 12,
  "created_at": "2026-06-14T10:00:00Z"
}
```

---

## GET /traces/{trace_id}

retrieval_trace 详情（含 request_snapshot、stages、response_summary）。

---

## POST /index/rebuild

管理员触发索引重建。

**Body**:

```json
{
  "object_types": ["ku", "wiki", "template_chapter"],
  "force_reembed": false
}
```

**Response `data`**: `{ "task_id": "uuid", "status": "queued" }`
