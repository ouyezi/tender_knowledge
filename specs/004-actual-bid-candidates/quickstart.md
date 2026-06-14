# Quickstart: Epic 3 实际标书导入与候选知识

**Feature**: `specs/004-actual-bid-candidates`  
**Purpose**: 端到端验证 确认 actual_bid → 解析 → 目录抽取 → 候选生成 → 目录编辑 → 只读候选列表

## Prerequisites

- Epic 0（产品分类 + 章节分类）与 Epic 1（File Import）已可用
- Epic 2 可选（Chapter Pattern 挖掘消费 Template Chapter）
- Docker & Docker Compose、Python 3.11+（`.venv`）、Node.js 20+
- 测试文件：实际标书 docx（或 `backend/tests/fixtures/sample-actual-bid.docx` 实现后添加）

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
| 候选知识中心（只读） | http://127.0.0.1:5173/candidates |

依赖（与 Epic 2 共享）：

```bash
.venv/bin/pip install python-docx lxml
```

LLM 配置（可选）：

```bash
LLM_PROVIDER=qwen
LLM_API_KEY=sk-...
LLM_MAX_CHUNK_CHARS=8000
```

## 测试

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "actual_bid or bid_outline or document_parse"
```

### Epic 3 + 005 联合验收（2026-06-14）

```bash
cd backend && ../.venv/bin/pytest \
  tests/integration/test_actual_bid_flow.py \
  tests/integration/test_actual_bid_outline_quality.py \
  tests/integration/test_bid_outline_structure_diff.py \
  tests/integration/test_bid_outline_parent_id.py \
  tests/unit/test_docx_document_walker.py \
  tests/unit/test_docx_toc_extractor.py \
  tests/unit/test_outline_heading_filter.py \
  -v
```

**期望**: 全部 PASS；鼎信 golden 离线测保留率 ≥95%、节点减少 ≥30%（合成 fixture）。

## 场景 0：Epic 1 前置 — 确认 actual_bid

见 [Epic 1 quickstart](../../002-source-import-classify/quickstart.md)。

```bash
export KB_ID="<active-kb-uuid>"
export OP=admin
export IMPORT_ID="<confirmed-actual-bid-import-id>"
```

**期望**: File Import `status=confirmed`，`file_purpose=actual_bid`；`downstream_entries` 含
`document_parse`、`bid_outline_extract`、`candidate_knowledge_generate` / `pending`。

## 场景 1：触发实际标书解析（P1）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/trigger" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"import_id\": \"${IMPORT_ID}\"}" | jq .
```

**期望**: 202；`parse_task_id` 存在；`status` 为 `pending` 或快速变为 `running`。

轮询直至 `ready`：

```bash
export PARSE_TASK_ID="<from-above>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/tasks/${PARSE_TASK_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '.data.status, .data.document_id, .data.bid_outline_id'
```

**期望**: `status=ready`；`document_id` 与 `bid_outline_id` 非空；downstream 三条均为 `completed`。

## 场景 2：查看 Document Tree（P1）

```bash
export DOCUMENT_ID="<from-above>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/documents/${DOCUMENT_ID}/tree" \
  -H "X-Operator-Id: ${OP}" | jq '.data.nodes | length, .data.nodes[0].node_type'
```

**期望**: 节点数 > 0；含 `heading` 类型节点；`source_type` 在 Document 详情中为 `actual_bid`。

## 场景 3：Bid Outline 编辑（P1）

```bash
export OUTLINE_ID="<bid_outline_id>"
export NODE_ID="<first-outline-node-id>"

curl -s -X PATCH \
  "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/bid-outlines/${OUTLINE_ID}/nodes/${NODE_ID}" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"title": "1. 总体技术方案（修订）"}' | jq '.data.title'
```

**期望**: 标题更新；再次 GET tree 一致；Document Tree 节点标题**未**自动变更。

## 场景 4：章节分类映射（P2）

```bash
export TAXONOMY_ID="<chapter-taxonomy-uuid>"

curl -s -X PATCH \
  "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/bid-outlines/${OUTLINE_ID}/nodes/${NODE_ID}" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"chapter_taxonomy_id\": \"${TAXONOMY_ID}\"}" | jq '.data.chapter_taxonomy_id'
```

**期望**: 映射持久化；审计日志可查（`actual_bid_audit_logs`）。

## 场景 5：候选知识只读列表（P2）

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/candidates?status=pending&source_channel=document" \
  -H "X-Operator-Id: ${OP}" | jq '.data.items | length, .data.items[0].source_trace'
```

**期望**: 至少 1 条 `pending` 候选（视样例 docx 章节而定）；`source_trace` 含 import/document/node；
管理台**无**确认按钮。

## 场景 6：重解析产生目录 diff（P1 Edge）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/trigger" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"import_id\": \"${IMPORT_ID}\", \"force_reparse\": true}" | jq .

# 轮询 ready 后
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/bid-outlines/${OUTLINE_ID}/diffs" \
  -H "X-Operator-Id: ${OP}" | jq '.data.items[0].status'
```

**期望**: 若结构有变，`diff` 为 `pending`；未 apply 前原人工编辑标题保持不变。

## 场景 7：Chapter Pattern 挖掘（P3）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/chapter-patterns/mine" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"min_frequency": 2}' | jq .

export MINING_TASK_ID="<from-above>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/chapter-patterns/mine/tasks/${MINING_TASK_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '.data.status, .data.result_summary'
```

**期望**: `status=completed`（有足够样本时 `patterns_created >= 1`）；模式 `status=candidate`。

## 场景 8：解析失败可恢复（SC-003）

模拟不可读文件或损坏 docx 后重试：

**期望**: `parse_task.status=failed` 且 `error_message` 非空；File Import 与 Document 记录仍存在；
可再次 `POST /trigger` 成功。

## 场景 9：未确认候选不参与检索（SC-006）

若存在检索占位 API：

```bash
# 实现后：检索 MUST 不返回 status=pending 的 candidate_knowledges
```

**期望**: 返回率为 0（本 Epic 仅验证列表 API 与检索隔离设计，完整检索在 Epic 5）。

## 相关文档

- 数据模型：[data-model.md](./data-model.md)
- API 契约：[contracts/](./contracts/)
- Epic 1 分流：[file-purpose-confirm-api.md](../../002-source-import-classify/contracts/file-purpose-confirm-api.md)
