# API Contract: Retrieval Eval & Strategy

**Base paths**:

- Eval: `/api/v1/kbs/{kb_id}/retrieval/eval`
- Strategy: `/api/v1/kbs/{kb_id}/retrieval/strategies`

**Version**: 1.0.0 (Epic 5)

---

## Strategy Versions

### GET /retrieval/strategies

策略版本列表。

**Query**: `is_active`, `page`, `page_size`

### POST /retrieval/strategies

创建策略版本。

**Body**:

```json
{
  "name": "default-v2",
  "version_tag": "2.0.0",
  "config": {},
  "embedding_config_version": "embed-v1",
  "rerank_config_version": null,
  "prompt_config_version": "prompt-v1",
  "notes": "提高 title BM25 权重"
}
```

### POST /retrieval/strategies/{strategy_version_id}/activate

激活策略（同 kb 其他版本 `is_active=false`）。

---

## Eval Sets

### GET /retrieval/eval/sets

评测集列表。

### POST /retrieval/eval/sets

**Body**: `{ "name": "核心检索用例", "description": "" }`

### GET /retrieval/eval/sets/{eval_set_id}/cases

评测用例列表。**Query**: `status`, `created_from`

### POST /retrieval/eval/sets/{eval_set_id}/cases

手工创建用例。

**Body**:

```json
{
  "query": "售后服务承诺",
  "intent": "knowledge_lookup",
  "filters": {},
  "expected_object_ids": ["uuid"],
  "negative_object_ids": [],
  "product_category_ids": ["uuid"],
  "chapter_taxonomy_ids": []
}
```

### POST /retrieval/eval/cases/{eval_case_id}/confirm

人工确认反馈来源用例进入正式评测集。

**Body**: `{ "confirmed_by": "admin" }`  
**Response**: `status=confirmed`, `confirmed_at` 填充。

### POST /retrieval/eval/cases/{eval_case_id}/reject

拒绝晋升用例。`status=rejected`。

---

## Eval Runs

### POST /retrieval/eval/runs

执行评测或策略对比。

**Body**:

```json
{
  "eval_set_id": "uuid",
  "strategy_version_id": "uuid",
  "baseline_strategy_version_id": "uuid",
  "k": 10,
  "metrics": ["recall_at_k", "precision_at_k", "mrr", "ndcg", "adoption_rate", "false_positive_rate", "false_negative_rate", "sourced_result_rate"]
}
```

**Response `data`**:

```json
{
  "eval_run_id": "uuid",
  "status": "running",
  "metrics": null,
  "comparison_metrics": null
}
```

### GET /retrieval/eval/runs/{eval_run_id}

**Response `data.metrics`** 示例：

```json
{
  "recall_at_k": 0.72,
  "precision_at_k": 0.65,
  "mrr": 0.58,
  "ndcg": 0.71,
  "adoption_rate": 0.42,
  "false_positive_rate": 0.08,
  "false_negative_rate": 0.12,
  "sourced_result_rate": 0.94
}
```

`comparison_metrics` 在提供 baseline 时包含各指标 delta。

**Errors**:

| Code | HTTP | When |
|------|------|------|
| EVAL_SET_EMPTY | 422 | 无 confirmed 用例 |
| STRATEGY_VERSION_NOT_FOUND | 404 | |
| EVAL_RUN_IN_PROGRESS | 409 | 同集合同策略正在运行 |
