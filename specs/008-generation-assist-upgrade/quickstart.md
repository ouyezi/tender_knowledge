# Quickstart: Epic 6 生成辅助升级

**Feature**: `specs/008-generation-assist-upgrade`  
**Purpose**: 端到端验证 招标约束录入 → 模块建议 → 采纳确认 → 变量填写 → 章节草稿生成 → 快照审计 → 接受/废弃

## Prerequisites

- Epic 0–5 已完成：已发布 KU/Wiki、Template Chapter（含 TemplateVariable）、
  Module Assembly Suggestion API 可用
- Epic 5 quickstart 场景 3 至少完成一次模块建议
- Docker Compose、Python 3.11+（`.venv`）、Node.js 20+
- **LLM**：配置 `LLM_PROVIDER` + API Key（qwen/openai/custom）；未配置时生成 API 返回
  `LLM_UNAVAILABLE`，场景 4 改用 mock 测试验证
- 测试 mock：`pytest` 默认 patch `llm_client`；见下方「Mock 测试路径」

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

## 测试

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "tender_requirement or generation or epic6"
```

## 场景 0：前置 — 环境变量

```bash
export KB_ID="<active-kb-uuid>"
export OP=admin
export CATEGORY_ID="<product-category-uuid>"
export TEMPLATE_CHAPTER_ID="<published-template-chapter-uuid>"
```

确认 Epic 5 索引与已发布资产就绪（参见 [Epic 5 quickstart](../../007-outline-retrieval-module-suggestion/quickstart.md) 场景 0–1）。

## 场景 1：创建招标约束（P1 / US1）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/tender-requirements" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{
    "title": "Epic6 验收招标约束",
    "outline_nodes": [
      {"title": "1. 技术方案", "level": 1, "sort_order": 0},
      {"title": "1.1 总体架构", "level": 2, "sort_order": 1}
    ],
    "score_points": [
      {"node_ref": "1.1 总体架构", "text": "架构清晰、可扩展，响应时间≤2秒"}
    ],
    "rejection_clauses": ["未提供资质证明废标"],
    "format_requirements": ["目录须三级编号"],
    "qualification_requirements": ["ISO9001 证书"],
    "response_clauses": ["须逐条响应技术规格书"]
  }' | jq '{requirement_context_id: .data.requirement_context_id}'
```

```bash
export REQ_CTX_ID="<requirement_context_id from above>"
```

**期望**: `requirement_context_id` 非空；`GET /tender-requirements/${REQ_CTX_ID}` 返回完整字段。

## 场景 2：模块组织建议与采纳（P1 / US1）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/module-suggestions" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"tender_requirement_context\": {
      \"score_points\": [\"架构清晰、可扩展，响应时间≤2秒\"],
      \"rejection_clauses\": [\"未提供资质证明废标\"]
    },
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"outline_nodes\": [
      {\"title\": \"1.1 总体架构\", \"level\": 2, \"sort_order\": 1}
    ],
    \"return_options\": {\"include_trace\": true, \"include_conflict_flags\": true}
  }" | jq '{suggestion_id: .data.module_suggestions[0].suggestion_id, risk_flags: .data.module_suggestions[0].risk_flags}'
```

```bash
export SUGGESTION_ID="<suggestion_id>"
```

采纳确认：

```bash
curl -s -X PATCH "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/module-suggestions/${SUGGESTION_ID}/adoption" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{"status": "adopted", "adoption_reason": "Epic6 quickstart 采纳"}' \
  | jq '.data.status'
```

**期望**: `adopted`；建议含 `hit_reason`、来源追溯；冲突时 `risk_flags` 非空。

## 场景 3：变量填写校验（P1 / US2）

查询 Template Chapter 变量（Epic 2 API）：

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-chapters/${TEMPLATE_CHAPTER_ID}/variables" \
  -H "X-Operator-Id: ${OP}" | jq '.data.items[] | {key: .variable_key, required: .required}'
```

尝试缺必填变量生成（应 422）：

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/drafts" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"requirement_context_id\": \"${REQ_CTX_ID}\",
    \"suggestion_id\": \"${SUGGESTION_ID}\",
    \"target_outline_node\": {\"title\": \"1.1 总体架构\", \"level\": 2, \"sort_order\": 1},
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"variable_values\": {}
  }"
```

**期望**: HTTP `422`，`code=MISSING_REQUIRED_VARIABLES`。

## 场景 4：章节草稿生成与轮询（P1 / US3）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/drafts" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d "{
    \"requirement_context_id\": \"${REQ_CTX_ID}\",
    \"suggestion_id\": \"${SUGGESTION_ID}\",
    \"target_outline_node\": {\"title\": \"1.1 总体架构\", \"level\": 2, \"sort_order\": 1},
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"variable_values\": {
      \"project_name\": \"Epic6 验收项目\",
      \"customer_name\": \"测试客户\"
    },
    \"manual_asset_compliance\": []
  }" | jq '{task_id: .data.task_id}'
```

```bash
export TASK_ID="<task_id>"

# 轮询直至 completed（LLM 配置时约 30s–3min）
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/tasks/${TASK_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '{status: .data.status, draft_id: .data.draft_id, snapshot_id: .data.snapshot_id}'
```

**期望**: `status=completed`；`draft_id` 与 `snapshot_id` 非空。

## 场景 5：草稿引用与快照审计（P1 / US4）

```bash
export DRAFT_ID="<draft_id>"
export SNAPSHOT_ID="<snapshot_id>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/drafts/${DRAFT_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '{
    paragraph_count: (.data.paragraphs | length),
    first_citations: .data.paragraphs[0].citations,
    conflict_hints: .data.conflict_hints
  }'

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/snapshots/${SNAPSHOT_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '{
    prompt_version: .data.prompt_version,
    variable_inputs: .data.variable_inputs,
    used_ku_count: (.data.used_ku_ids | length)
  }'
```

**期望**: 每段 `citations` 非空；snapshot 含 `prompt_version`、`variable_inputs`、
`requirement_context_snapshot`。

## 场景 6：接受与重新生成（P2 / US6）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/drafts/${DRAFT_ID}/accept" \
  -H "X-Operator-Id: ${OP}" | jq '.data.outcome_status'

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/generation/drafts/${DRAFT_ID}/regenerate" \
  -H "Content-Type: application/json" \
  -H "X-Operator-Id: ${OP}" \
  -d '{"variable_values": {"project_name": "Epic6 验收项目 v2"}}' \
  | jq '{new_task_id: .data.task_id}'
```

**期望**: accept 后 `outcome_status=accepted`；regenerate 产生新 task，旧 snapshot 仍可查。

## 场景 7：招标-模板冲突优先级（P1 / US3 / SC-003）

使用含已知冲突废标项的招标约束 + 含冲突内容的 Template Chapter seed（见
`test_generation_conflict_priority.py`）：

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_generation_conflict_priority.py -v
```

**期望**: 草稿 `conflict_hints` 非空；未静默采用冲突模板正文。

## Mock 测试路径（无 LLM Key）

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_epic6_quickstart_flow.py -v
```

集成测试 patch `llm_client.chat_completion` 返回固定 JSON paragraphs，验证
task 状态流转、citation 结构、snapshot 字段完整性。

## UI 验证（可选）

1. 打开 http://127.0.0.1:5173/outlines
2. 进入模块建议向导 → 录入招标约束 → 生成建议 → 采纳
3. 填写变量 → 发起生成 → 查看草稿段落引用
4. 打开快照 Drawer → 确认变量与 prompt_version
5. 接受或废弃 → 重新生成

## 相关文档

- 数据模型：[data-model.md](./data-model.md)
- API 契约：[tender-requirement-api.md](./contracts/tender-requirement-api.md)、
  [generation-api.md](./contracts/generation-api.md)
- Epic 5 前置：[quickstart.md](../../007-outline-retrieval-module-suggestion/quickstart.md)
