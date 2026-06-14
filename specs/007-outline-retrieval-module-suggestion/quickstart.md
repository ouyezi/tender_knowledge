# Quickstart: Epic 5 目录级检索与模块建议

**Feature**: `specs/007-outline-retrieval-module-suggestion`  
**Purpose**: 端到端验证 知识检索 → 目录匹配 → 模块建议 → trace 追溯 → 反馈 → 评测对比

## Prerequisites

- Epic 0–4 已完成：存在 **已发布** KU/Wiki、Bid Outline、Template Chapter、Chapter Pattern
- Epic 4 quickstart 场景 3 至少发布 1 条 KU（`searchable=true`）
- Docker Compose（**pgvector** 镜像）、Python 3.11+（`.venv`）、Node.js 20+
- 可选：`EMBEDDING_API_BASE` / `EMBEDDING_API_KEY` 启用向量召回；未配置时仅关键词+结构匹配

## 一键启动

```bash
python -m venv .venv
.venv/bin/pip install -e "backend/[dev]"
cd frontend && npm install && cd ..
./scripts/start.sh
```

| 服务 | 地址 |
|------|------|
| API Health | http://127.0.0.1:8000/health |
| OpenAPI | http://127.0.0.1:8000/docs |
| 目录中心 | http://127.0.0.1:5173/outlines |
| 检索优化中心 | http://127.0.0.1:5173/retrieval-optimization |

## 测试

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "retrieval or module_suggestion or eval"
```

## 场景 0：前置 — 索引与已发布资产

```bash
export KB_ID="<active-kb-uuid>"
export OP=admin
export CATEGORY_ID="<product-category-uuid>"

# 确认有已发布 KU
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/knowledge-units?page_size=5" | jq '.data.total'

# 触发索引重建（首次或迁移后）
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/index/rebuild" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{"object_types":["ku","wiki","template_chapter","bid_outline","chapter_pattern"]}' | jq '.data.status'
```

**期望**: KU total ≥ 1；索引任务 `queued` 或 `success`。

## 场景 1：知识检索与产品分类过滤（P1 / US1）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/search" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"query\": \"技术方案\",
    \"intent\": \"knowledge_lookup\",
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"retrieval_options\": { \"top_k\": 10, \"enable_bm25\": true, \"enable_vector\": false },
    \"return_options\": { \"include_trace\": true, \"include_score_detail\": true, \"include_knowledge_pack\": true }
  }" | jq '{trace_id: .data.trace_id, count: (.data.items | length), first_score: .data.items[0].score}'
```

**期望**: `trace_id` 非空；结果含 `score`、`score_detail`、`hit_reason`、`knowledge_pack`；
不适用产品分类的素材不出现。

## 场景 2：目录级匹配与缺失章节（P1 / US1 + US3）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/directory-match" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"outline_nodes\": [
      {\"title\": \"1. 技术方案\", \"level\": 1},
      {\"title\": \"1.1 总体架构\", \"level\": 2}
    ],
    \"return_options\": { \"include_trace\": true, \"include_score_detail\": true }
  }" | jq '.data.directory_match | {match_score, coverage_rate, missing: (.missing_chapters | length)}'
```

**期望**: `match_score`、`coverage_rate`、`score_detail` 均有值；若有高频未覆盖 Pattern，
`missing_chapters` 非空。

## 场景 3：模块组织建议（P1 / US2）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/module-suggestions" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"project_type\": \"government\",
    \"customer_type\": \"enterprise\",
    \"outline_nodes\": [
      {\"title\": \"1. 技术方案\", \"level\": 1, \"sort_order\": 0}
    ],
    \"tender_requirement_context\": {
      \"score_points\": [\"须描述系统架构\"],
      \"rejection_clauses\": [\"未提供资质证明废标\"],
      \"format_requirements\": []
    },
    \"return_options\": { \"include_trace\": true, \"include_conflict_flags\": true }
  }" | jq '{trace_id: .data.trace_id, suggestions: (.data.module_suggestions | length), latency_ms: .data.latency_ms}'
```

**期望**: `module_suggestions` ≥ 1；含 `match_score`、`coverage_rate`、`score_point_coverage`；
`latency_ms` 典型 < 2000（无 LLM）。

## 场景 4：retrieval_trace 查询（P2 / US4）

```bash
export TRACE_ID="<from-scenario-1-or-3>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/traces/${TRACE_ID}" \
  | jq '{intent: .data.intent, stages: .data.stages, request: .data.request_snapshot.intent}'
```

**期望**: 可见完整 `request_snapshot` 与 `stages` 召回/排序摘要。

## 场景 5：检索反馈（P2 / US5）

```bash
export KU_ID="<ku-uuid-from-search>"

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/feedback" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"trace_id\": \"${TRACE_ID}\",
    \"feedback_type\": \"useful\",
    \"object_type\": \"ku\",
    \"object_id\": \"${KU_ID}\",
    \"rank_position\": 1
  }" | jq '.data.feedback_id'
```

**期望**: 返回 `feedback_id`；GET traces 同 trace 可关联反馈列表。

## 场景 6：评测集与策略版本对比（P2 / US6）

```bash
# 创建评测集与用例（需先手工创建 eval_set_id）
export EVAL_SET_ID="<eval-set-uuid>"
export STRATEGY_A="<strategy-version-uuid>"
export STRATEGY_B="<baseline-strategy-version-uuid>"

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/eval/runs" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"eval_set_id\": \"${EVAL_SET_ID}\",
    \"strategy_version_id\": \"${STRATEGY_A}\",
    \"baseline_strategy_version_id\": \"${STRATEGY_B}\",
    \"k\": 10
  }" | jq '.data.eval_run_id'
```

**期望**: 评测完成后 `metrics` 含 Recall@K、NDCG 等；对比时 `comparison_metrics` 有 delta。

## 场景 7：候选知识隔离（负向）

```bash
# 存在 pending 候选但不应被检索
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates?status=pending&page_size=1" \
  | jq -r '.data.items[0].candidate_id // empty' | read PENDING_ID

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/retrieval/search" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"test\",\"intent\":\"knowledge_lookup\",\"retrieval_options\":{\"top_k\":50}}" \
  | jq '[.data.items[].object_id] | index("'"${PENDING_ID}"'") // "not_found"'
```

**期望**: 输出 `"not_found"`（pending 候选 ID 不在检索结果中）。

## UI 验证（可选）

1. **目录中心** → 选择 Bid Outline → 「目录相似度」查看 match_score / coverage_rate。
2. **检索优化中心** → 打开 trace 详情 → 提交有用/误召回反馈 → 晋升评测用例并确认。
3. **模块建议** → 输入招标评分点 → 确认 risk_flags 在模板冲突时出现。

## 相关文档

- [retrieval-api.md](./contracts/retrieval-api.md)
- [module-suggestion-api.md](./contracts/module-suggestion-api.md)
- [retrieval-feedback-api.md](./contracts/retrieval-feedback-api.md)
- [retrieval-eval-api.md](./contracts/retrieval-eval-api.md)
- [data-model.md](./data-model.md)
- Epic 4 quickstart（发布前置）: [../../006-candidate-confirm-workbench/quickstart.md](../../006-candidate-confirm-workbench/quickstart.md)
