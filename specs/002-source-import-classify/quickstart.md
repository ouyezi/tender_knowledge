# Quickstart: Epic 1 来源导入与文件分类确认

**Feature**: `specs/002-source-import-classify`  
**Purpose**: 端到端验证单文件上传 → 建议 → 确认 → 分流占位

## Prerequisites

- Epic 0 已可用（产品分类 + 章节分类）
- Docker & Docker Compose、Python 3.11+（`.venv`）、Node.js 20+
- 准备测试文件：`fixtures/sample-template.docx`、`fixtures/sample-bid.pdf`（任意小文件即可）

## 一键启动

```bash
# 依赖（若未安装）
python -m venv .venv
.venv/bin/pip install -e "backend/[dev]"
cd frontend && npm install && cd ..

# 启动（Epic 1 实现后含 upload volume）
./scripts/start.sh
```

| 服务 | 地址 |
|------|------|
| API Health | http://127.0.0.1:8000/health |
| OpenAPI | http://127.0.0.1:8000/docs |
| 管理后台 | http://127.0.0.1:5173 |
| 来源导入中心 | http://127.0.0.1:5173/file-imports |

环境变量（Epic 1 新增）：

```bash
STORAGE_ROOT=data/uploads          # 默认
FILE_SIZE_LIMIT_MB=50              # 默认按类型见 research R7
```

## 测试

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k file_import
```

## 场景 1：上传并获取 import_id（P1）

```bash
export KB_ID="<active-kb-uuid>"
export OP=admin

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports" \
  -H "X-Operator-Id: ${OP}" \
  -F "file=@fixtures/sample-template.docx" | jq .
```

**期望**: 201；`data.import_id` 存在；`status` 为 `uploaded`；响应 < 5s。

轮询直至建议就绪：

```bash
export IMPORT_ID="<from-above>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports/${IMPORT_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '.data.status, .data.suggestion'
```

**期望**: `need_confirm`；`suggestion` 非 null。

## 场景 2：用途确认与分流（P2/P3）

```bash
export VERSION=$(curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports/${IMPORT_ID}" \
  -H "X-Operator-Id: ${OP}" | jq '.data.version')

curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports/${IMPORT_ID}/confirm" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{
    \"expected_version\": ${VERSION},
    \"file_purpose\": \"template_file\",
    \"product_category_ids\": [],
    \"enter_parsing\": true
  }" | jq .
```

**期望**: `status=confirmed`；`downstream_entries_created` 含 `template_file_parse`。

验证下游占位：

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports/${IMPORT_ID}/downstream-entries" \
  -H "X-Operator-Id: ${OP}" | jq .
```

## 场景 3：忽略文件

上传后调用 `POST .../ignore`。

**期望**: `status=ignored`；`downstream-entries` 为空。

## 场景 4：重复文件

同一文件上传两次（不带 `duplicate_action`）。

**期望**: 第二次 `409 DUPLICATE_FILE`；带 `duplicate_action=new_version` 时创建新 `import_id` 且 `version_no` 递增。

## 场景 5：任务日志与重试

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports/${IMPORT_ID}/tasks" \
  -H "X-Operator-Id: ${OP}" | jq .
```

失败记录：

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/file-imports/${IMPORT_ID}/retry" \
  -H "X-Operator-Id: ${OP}" | jq .
```

## UI 验收（管理后台）

1. 打开 **来源导入中心** → 上传 docx。
2. 列表显示「待确认」状态。
3. 进入确认页：查看建议 → 修改用途/分类 → 保存。
4. 状态变为「已确认」；任务抽屉可查看 `file_import` / `file_purpose_classify` 日志。
5. 上传重复文件 → 弹窗选择跳过或新版本。

## Epic 集成检查点

| 检查项 | 验证方式 |
|--------|----------|
| Epic 0 分类可选 | 确认页下拉来自 product-categories / chapter-taxonomies API |
| Epic 2 可消费 template_file | `downstream_entries.task_type=template_file_parse` 且 `pending` |
| Epic 3 可消费 actual_bid | 确认 actual_bid 后存在 `document_parse` 等条目 |
| 审计追溯 | `import_audit_log` 或 API 返回 `trace_id` 可关联操作 |

## 相关文档

- 数据模型：[data-model.md](./data-model.md)
- API 契约：[file-import-api.md](./contracts/file-import-api.md)、
  [file-purpose-confirm-api.md](./contracts/file-purpose-confirm-api.md)
- 技术决议：[research.md](./research.md)
