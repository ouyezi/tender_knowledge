# API Contract: Module Assembly Suggestion

**Base path**: `/api/v1/kbs/{kb_id}/module-suggestions`  
**Version**: 1.0.0 (Epic 5)

共用约定见 [retrieval-api.md](./retrieval-api.md)。

---

## POST /

生成模块组织建议（无 LLM 编排路径）。

**Body**:

```json
{
  "tender_requirement_context": {
    "outline_nodes": [],
    "score_points": ["响应时间≤2秒"],
    "rejection_clauses": ["未提供资质证明废标"],
    "format_requirements": ["目录须三级编号"]
  },
  "product_category_ids": ["uuid"],
  "project_type": "government",
  "customer_type": "enterprise",
  "outline_nodes": [
    { "title": "1. 技术方案", "level": 1, "sort_order": 0 },
    { "title": "1.1 总体架构", "level": 2, "sort_order": 1 }
  ],
  "requirement_text": "补充说明文本",
  "retrieval_options": {
    "strategy_version_id": "uuid",
    "top_k": 10
  },
  "return_options": {
    "include_trace": true,
    "include_score_detail": true,
    "include_conflict_flags": true
  }
}
```

**Response `data`**:

```json
{
  "trace_id": "uuid",
  "module_suggestions": [
    {
      "suggestion_id": "uuid",
      "target_outline_node": {
        "title": "1.1 总体架构",
        "level": 2,
        "sort_order": 1
      },
      "suggested_template_chapter_ids": ["uuid"],
      "suggested_ku_ids": ["uuid"],
      "suggested_wiki_ids": [],
      "suggested_manual_asset_ids": [],
      "suggested_bid_outline_node_ids": ["uuid"],
      "suggested_chapter_pattern_ids": ["uuid"],
      "organization_hint": {
        "order": ["ku", "wiki"],
        "grouping": "按子节展开"
      },
      "match_score": 0.85,
      "coverage_rate": 0.8,
      "score_detail": {
        "product_category": 0.3,
        "chapter_taxonomy": 0.28,
        "title_similarity": 0.17,
        "level_order": 0.1,
        "knowledge_coverage": 0.05
      },
      "score_point_coverage": [
        { "score_point": "响应时间≤2秒", "covered": true, "matched_object_ids": ["uuid"] }
      ],
      "rejection_risks": [],
      "risk_flags": [],
      "hit_reason": "历史标书同章节模块与模板章节高度匹配",
      "available_ku_count": 3,
      "available_wiki_count": 1,
      "knowledge_pack_items": []
    }
  ],
  "missing_chapters": [],
  "latency_ms": 890
}
```

**Errors**:

| Code | HTTP | When |
|------|------|------|
| EMPTY_OUTLINE | 422 | outline_nodes 为空 |
| TEMPLATE_CONFLICT | 200 | 非错误；risk_flags 非空表示存在招标-模板冲突 |
| SUGGESTION_FAILED | 500 | 编排失败 |

---

## GET /{suggestion_id}

查询已持久化的单条模块建议（Epic 6 衔接）。

---

## GET /

按 trace_id 或时间范围列表查询历史建议。

**Query**: `trace_id`, `from`, `to`, `page`, `page_size`
