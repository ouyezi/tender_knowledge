# Quickstart: Epic 4 候选知识确认工作台

**Feature**: `specs/006-candidate-confirm-workbench`  
**Purpose**: 端到端验证 候选列表筛选 → 编辑 → 单条发布 → 合并/忽略 → 批量确认 → 审计日志 → 检索隔离

## Prerequisites

- Epic 0（产品分类 + 章节分类）
- Epic 1（File Import 确认）
- Epic 2 或 Epic 3 已产生 **pending** Candidate Knowledge（document 和/或 template stub）
- Docker & Docker Compose、Python 3.11+（`.venv`）、Node.js 20+

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
| 候选知识确认工作台 | http://127.0.0.1:5173/candidates |

## 测试

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "candidate_confirm or candidate_publish or candidate_batch"
```

## 场景 0：前置 — 确保有待确认候选

完成 [Epic 3 quickstart](../../004-actual-bid-candidates/quickstart.md) 场景 1–4，或
[Epic 2 quickstart](../../003-template-parse-publish/quickstart.md) 模板解析确认，使列表存在
`status=pending` 条目。

```bash
export KB_ID="<active-kb-uuid>"
export OP=admin
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates?status=pending" | jq '.data.total'
```

**期望**: total ≥ 1。

## 场景 1：筛选候选列表（P1）

```bash
export IMPORT_ID="<import-uuid>"
export TAXONOMY_ID="<chapter-taxonomy-uuid>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates?status=pending&import_id=${IMPORT_ID}&chapter_taxonomy_id=${TAXONOMY_ID}" \
  | jq '.data.items | length'
```

**期望**: 返回满足全部筛选条件的子集；响应含 `candidate_id`、`source_channel`、
`confidence_score`。

## 场景 2：编辑候选详情（P1）

```bash
export CANDIDATE_ID="doc_<uuid>"

curl -s -X PATCH "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates/${CANDIDATE_ID}" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{"title":"修订标题","summary":"修订摘要"}' | jq '.data.status'
```

**期望**: `"pending"`；再次 GET 详情可见更新标题。

## 场景 3：发布为 Knowledge Unit（P1）

```bash
export CATEGORY_ID="<product-category-uuid>"

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates/${CANDIDATE_ID}/confirm" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"confirm_as\": \"ku\",
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"chapter_taxonomy_id\": \"${TAXONOMY_ID}\",
    \"knowledge_type\": \"solution\",
    \"searchable\": true,
    \"review_comment\": \"quickstart 单条发布\"
  }" | jq '{status: .data.status, object: .data.confirmed_object_id, trace: .data.trace_id}'
```

**期望**:

- `status` = `"published"`
- `confirmed_object_id` 非空
- 候选列表 `status=pending` 不再包含该 ID
- GET KU（实现后）可见 `candidate_id` 来源字段

## 场景 4：忽略候选（P2）

```bash
export IGNORE_ID="doc_<another-uuid>"

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates/${IGNORE_ID}/confirm" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{"confirm_as":"ignore","review_comment":"低价值忽略"}' | jq '.data.status'
```

**期望**: `"rejected"`。

## 场景 5：合并候选（P2）

```bash
export TARGET="doc_<target-uuid>"
export SOURCE="doc_<source-uuid>"

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates/merge" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"target_candidate_id\": \"${TARGET}\",
    \"source_candidate_ids\": [\"${SOURCE}\"],
    \"review_comment\": \"重复段落合并\"
  }" | jq '.data.merged_count'
```

**期望**: `merged_count` = 1；SOURCE 状态为 merged。

## 场景 6：批量确认（P2）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates/batch/confirm" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{
    "items": [
      {"candidate_id":"doc_<id1>","confirm_as":"ku","knowledge_type":"solution","product_category_ids":["'"${CATEGORY_ID}"'"],"chapter_taxonomy_id":"'"${TAXONOMY_ID}"'"},
      {"candidate_id":"doc_<id2>","confirm_as":"ignore"}
    ],
    "batch_comment": "quickstart batch"
  }' | jq '{batch_id: .data.batch_id, succeeded: .data.succeeded, failed: .data.failed}'
```

**期望**: 30s 内返回汇总；`batch_id` 可用于审计查询。

## 场景 7：审计日志（P3）

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidate-audit-logs?candidate_id=${CANDIDATE_ID}" \
  | jq '.data.items[].action'
```

**期望**: 含 `publish`（及先前 `edit` 若执行过场景 2）。

## 场景 8：发布失败重试（P1）

人为构造校验失败（如缺少 `knowledge_type`），确认 `last_publish_error` 写入后：

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates/${CANDIDATE_ID}/retry-publish" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{"confirm_as":"ku","knowledge_type":"solution","product_category_ids":["'"${CATEGORY_ID}"'"],"chapter_taxonomy_id":"'"${TAXONOMY_ID}"'"}' \
  | jq '.data.status'
```

**期望**: 第二次成功为 `"published"`；审计含 `publish_failed` 与 `publish` 两条。

## 场景 9：检索隔离（Constitution）

```bash
# 待确认候选 MUST NOT 出现在正式 KU 列表（Epic 5 前用 KU list API 负向测试）
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/knowledge-units?status=published" \
  | jq '[.data.items[] | select(.candidate_id == "<pending-candidate-uuid>")] | length'
```

**期望**: `0`（pending 候选 ID 不出现在正式 KU）。

## UI 验收清单

- [x] `/candidates` 列表筛选（批次、分类、章节、类型、状态）
- [x] 详情抽屉编辑并保存
- [x] 发布面板选择 confirm_as 并成功发布
- [x] 合并/拆分 Modal
- [x] 多选批量确认/驳回 + 结果汇总
- [x] 操作日志 Tab 可按 candidate_id 过滤

## 相关契约

- [candidate-confirm-api.md](./contracts/candidate-confirm-api.md)
- [candidate-batch-api.md](./contracts/candidate-batch-api.md)
- [candidate-audit-api.md](./contracts/candidate-audit-api.md)
- [data-model.md](./data-model.md)
