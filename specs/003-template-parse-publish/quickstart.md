# Quickstart: Epic 2 模板库解析与发布

**Feature**: `specs/003-template-parse-publish`  
**Purpose**: 端到端验证 确认 template_file → 解析 → 人工确认 → 编辑 → 发布

## Prerequisites

- Epic 0（产品分类 + 章节分类）与 Epic 1（File Import）已可用
- Docker & Docker Compose、Python 3.11+（`.venv`）、Node.js 20+
- 测试文件：`backend/tests/fixtures/sample-template.docx`

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
| 模板库中心 | http://127.0.0.1:5173/template-libraries |

Epic 2 新增依赖（实现后）：

```bash
.venv/bin/pip install python-docx
```

## 测试

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k template
```

## 场景 0：Epic 1 前置 — 确认 template_file

见 [Epic 1 quickstart](../../002-source-import-classify/quickstart.md) 场景 1–2。

```bash
export KB_ID="<active-kb-uuid>"
export OP=admin
export IMPORT_ID="<confirmed-template-file-import-id>"
```

**期望**: File Import `status=confirmed`，`file_purpose=template_file`；
`downstream_entries` 含 `template_file_parse` / `pending`。

## 场景 1：触发模板解析（P1）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-parse/trigger" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"import_id\": \"${IMPORT_ID}\"}" | jq .
```

**期望**: 202；`parse_task_id` 存在；`status` 为 `pending` 或快速变为 `running`。

轮询任务直至 `parse_ready`：

```bash
export PARSE_TASK_ID="<from-above>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-parse/tasks/${PARSE_TASK_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '.data.status, .data.suggestion != null'
```

**期望**: `parse_ready`；章节树非空；原 File Import 仍可 GET。

## 场景 2：人工确认解析结果（P2）

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-parse/tasks/${PARSE_TASK_ID}/suggestion" \
  -H "X-Operator-Id: ${OP}" | jq '.data.suggested_chapter_tree | length'
```

提交确认（按 suggestion 调整 chapters）：

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-parse/tasks/${PARSE_TASK_ID}/confirm" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d @fixtures/template-parse-confirm-payload.json | jq .
```

**期望**: `status=confirmed`；`template_id` 非空；`structure_locked_at` 有值。

## 场景 3：章节树编辑（P3）

```bash
export TEMPLATE_ID="<from-confirm>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/templates/${TEMPLATE_ID}/chapters/tree" \
  -H "X-Operator-Id: ${OP}" | jq '.data.roots | length'

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/templates/${TEMPLATE_ID}/chapters/batch-update" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d @fixtures/template-chapter-batch-update.json | jq .
```

**期望**: 保存后再次 GET tree 与编辑一致；`template_audit_log` 有 `chapter_update`。

## 场景 4：模板库创建与发布（P4）

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-libraries" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"library_name":"测试模板库","library_type":"technical"}' | jq .

export LIB_ID="<library-id>"

curl -s -X PATCH "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/templates/${TEMPLATE_ID}" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"template_library_id\": \"${LIB_ID}\"}" | jq .

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/templates/${TEMPLATE_ID}/variables" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"variable_key":"project_name","display_name":"项目名称","required":true,"default_value":""}' | jq .

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/template-libraries/${LIB_ID}/publish" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"cascade_templates":true}' | jq .
```

**期望**: Library `status=published`；`snapshot_id` 存在；
`GET .../template-libraries?status=published` 可查到。

## 场景 5：解析失败与重试

模拟不可读 storage_path 或损坏 docx。

**期望**: `parse_task.status=failed`；File Import 仍可 GET；`POST .../retry` 可重新排队。

## 场景 6：重解析 diff（Edge Case）

对已 `structure_locked` 的 Template 再次 `trigger` + `force_reparse=true`。

**期望**: 返回 `structure_diff.status=pending_review`；原章节树不变直至 `diff/apply`。

## UI 验收（模板库中心）

1. 打开 **模板库中心** → 查看 Template Library 列表与未归类 Template。
2. 从 File Import 或解析任务入口进入 **解析确认** 抽屉 → 修正章节树 → 保存。
3. **章节树编辑器** 调整层级/类型/排序 → 保存刷新一致。
4. 配置变量与规则 → **发布** 模板库 → 查看版本快照。
5. 未发布库在「仅已发布」筛选中不可见。

## Epic 集成检查点

| 检查项 | 验证方式 |
|--------|----------|
| Epic 1 下游 | `template_file_parse` entry 被 claim 并完成 |
| Epic 4 候选 | `candidate-stubs?status=pending_confirm` 有记录 |
| Epic 5 只读 | 仅 `published` library/chapters 可查询 |
| 审计 | `template_audit_log` / `trace_id` 关联 parse→confirm→publish |
| G3 人工门 | `parse_ready` 前无 published 资产 |

## 相关文档

- 数据模型：[data-model.md](./data-model.md)
- API 契约：[template-parse-api.md](./contracts/template-parse-api.md)、
  [template-library-api.md](./contracts/template-library-api.md)、
  [template-chapter-api.md](./contracts/template-chapter-api.md)、
  [template-asset-api.md](./contracts/template-asset-api.md)
- 技术决议：[research.md](./research.md)
