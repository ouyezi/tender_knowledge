# Design: E2E 导入→知识发布→检索 全自动验收脚本

**Date**: 2026-06-14  
**Status**: Approved (brainstorming)  
**Related scripts**: `scripts/quickstart-epic3-verify.sh`, `scripts/quickstart-epic4-dingxin-verify.sh`, `scripts/bootstrap-dingxin-candidates.py`, `scripts/epic6_live_acceptance.py`  
**Constitution refs**: II Knowledge Asset First, III Human Confirmation Gate (测试环境 API 自动 confirm), V Retrieval Before Generation

## 1. 背景与目标

平台 MVP 链路为：单文件导入 → 用途确认 → 解析 → 候选知识 → 人工确认发布 → 检索。
现有验收脚本分散在 Epic 3/4 quickstart bash 与 pytest integration 中，**未贯通至检索**，
且日志为终端 `✅/❌`，不利于智能体读取上下文做错误排查。

**目标**：交付单一可执行脚本，对**实际标书**或**模板文件**跑通完整链路，输出结构化
JSON Lines 日志，供 agent 定位失败步骤、HTTP 上下文与业务 ID。

## 2. Brainstorming 决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 运行模式 | **混合 C**：默认 Live API；`--mode=integration` 走 pytest/TestClient |
| D2 | 文件用途 | **两者 C**：`--purpose actual_bid \| template_file` |
| D3 | 人工确认门 | **全自动 A**：脚本调用 confirm API 发布，不依赖 UI |
| D4 | 日志格式 | **仅 JSONL A**：不写 Markdown 报告；终端仅一行摘要 |
| D5 | 服务依赖 | **自动拉起 B**：调用 `scripts/start.sh`（E2E 设 `SKIP_FRONTEND=1`） |
| D6 | 检索断言 | **动态 + 冒烟 C**：发布标题关键词 query + 固定「技术方案」query |
| D7 | 实现路径 | **方案 1**：Python 编排器 + `scripts/lib/e2e/` 模块化 Step 库 |

## 3. 实现路径对比

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **① Python 编排器（采用）** | `e2e_pipeline_test.py` + step 库 + ApiClient 抽象 | JSONL 自然；hybrid 易实现；吸收 epic3 fallback | 需一次性整理 bash |
| ② Bash 链式 | 顺序调用 epic3/4 sh | 改动小 | JSONL 脆弱；无模板链；难 hybrid |
| ③ pytest 为主 | `-m live_e2e` | CI 原生 | 非独立脚本；bootstrap awkward |

## 4. CLI 与入口

**主入口**：`scripts/e2e_pipeline_test.py`

```bash
.venv/bin/python scripts/e2e_pipeline_test.py \
  --file /path/to/doc.docx \
  --purpose actual_bid \
  --kb-id <uuid> \
  [--mode live|integration] \
  [--auto-publish-count 1] \
  [--keep-services] \
  [--log-file logs/e2e-<run_id>.jsonl]
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--file` | 按 purpose 选 fixture | `sample-actual-bid.docx` / `sample-template.docx` |
| `--purpose` | 必填 | `actual_bid` \| `template_file` |
| `--kb-id` | 环境变量 `KB_ID` 或 seeded KB | Live 模式目标知识库 |
| `--mode` | `live` | `integration` 不启动服务，用 TestClient |
| `--auto-publish-count` | `1` | 自动 confirm 的候选条数 |
| `--keep-services` | false | Live 结束后不调用 `scripts/stop.sh` |
| `--log-file` | `logs/e2e-<run_id>.jsonl` | JSONL 输出路径 |

**退出码**：`0` 全通过；`1` 业务步骤失败；`2` preflight/环境失败。

## 5. 流程架构

```text
preflight + bootstrap_services (live only)
  → upload + confirm_import (file_purpose)
  → [branch] parse pipeline
  → list_candidates (pending ≥ 1)
  → auto_publish (confirm API × N)
  → retrieval_dynamic (title keyword)
  → retrieval_smoke (固定「技术方案」)
  → run_summary
```

### 5.1 共用步骤

| Step | Live API | 失败策略 |
|------|----------|----------|
| `preflight` | GET `/health`；校验 KB | exit 2 |
| `bootstrap_services` | `SKIP_FRONTEND=1 scripts/start.sh` | exit 2 |
| `upload` | POST `file-imports` | fail-fast |
| `confirm_import` | POST `file-imports/{id}/confirm` | fail-fast |
| `list_candidates` | GET `candidates?status=pending&import_id=` | fail-fast |
| `auto_publish` | POST `candidates/{id}/confirm` | fail-fast |
| `retrieval_dynamic` | POST `retrieval/search` | fail-fast |
| `retrieval_smoke` | POST `retrieval/search` | fail-fast |
| `run_summary` | 汇总 | 写最后一行 jsonl |

### 5.2 `actual_bid` 分支

1. `parse_trigger` — confirm 返回的 `actual_bid_parse_task_id` 或 POST `actual-bid-parse/trigger`
2. `parse_poll` — 轮询至 `ready`/`confirmed`；超时则 `parse_runner_fallback`（同步调用 `actual_bid_parse_runner._run_entry`，与 epic3 一致）
3. `parse_wizard_confirm` — POST `actual-bid-parse/tasks/{id}/confirm`（outline_nodes 取自 API）
4. `taxonomy_backfill` — 对 document tree heading 回填 `chapter_taxonomy_id` / `product_category_ids`（逻辑参数化自 `bootstrap-dingxin-candidates.py`，非硬编码 import_id）
5. `candidate_generate` — 若 API 未自动生成 pending，调用 `candidate_generate_service.generate_for_document`

### 5.3 `template_file` 分支

1. `template_parse_trigger` — confirm 后 template parse 入队或 POST `template-parse/trigger`
2. `template_parse_poll` — 轮询至 `ready`/`confirmed`；超时则 `template_parse_runner_fallback`
3. `template_parse_confirm` — POST `template-parse/tasks/{id}/confirm`（按 API 契约提交 suggestion）
4. `list_candidates` — `source_channel=template` 筛选

发布类型：`actual_bid` 默认 `confirm_as=ku`；`template_file` 默认 `confirm_as=template_chapter`（无可用候选时降级 `ku` 并写 `step` warning 事件）。

### 5.4 Parse runner fallback

Live 模式下 background task 可能未消费队列。与 epic3 相同：查 `downstream_task_entries` pending 条目，同步 `_run_entry` 后重试 poll。fallback 本身写独立 jsonl 事件 `parse_runner_fallback`。

## 6. 模块结构

```text
scripts/
  e2e_pipeline_test.py          # CLI 入口
  lib/
    e2e/
      __init__.py
      client.py                 # ApiClient 协议；LiveClient / IntegrationClient
      logger.py                 # JsonlRunLogger
      runner.py                 # E2EPipelineRunner
      steps/
        common.py               # upload, confirm, publish, retrieval
        actual_bid.py             # parse, wizard, taxonomy, candidate generate
        template_file.py          # template parse branch
      fallback.py               # parse runner 同步执行
```

**ApiClient 抽象**（供 hybrid 复用）：

```python
class ApiClient(Protocol):
    def request(self, method: str, path: str, *, json: dict | None = None, ...) -> ApiResponse: ...
```

- `LiveClient`：`urllib` 或 `httpx`，base `http://127.0.0.1:8000`
- `IntegrationClient`：pytest `TestClient`，由 `--mode integration` 在进程内构造

## 7. JSONL 事件规范

每行一个 JSON 对象；**终端仅打印** `[step_name] ok|FAILED (duration_ms)`。

### 7.1 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts` | ISO8601 UTC | 事件时间 |
| `run_id` | UUID | 本次运行 ID |
| `step` | string | 步骤名 |
| `status` | `ok` \| `failed` \| `skipped` \| `warning` | |
| `duration_ms` | int | 步骤耗时 |
| `purpose` | string | `actual_bid` \| `template_file` |
| `mode` | string | `live` \| `integration` |
| `context` | object | 累积业务 ID（见下） |
| `http` | object? | method, path, status_code, response_excerpt (≤2KB) |
| `assertion` | object? | name, expected, actual |
| `error` | object? | type, message, traceback |

### 7.2 `context` 键（按进展填充）

`kb_id`, `import_id`, `document_id`, `parse_task_id`, `bid_outline_id`, `template_id`,
`candidate_ids[]`, `published_object_ids[]`, `retrieval_trace_ids[]`, `query_used`

### 7.3 终止事件 `run_summary`

```json
{
  "step": "run_summary",
  "status": "ok",
  "steps_total": 12,
  "steps_passed": 12,
  "steps_failed": 0,
  "failed_step": null,
  "log_file": "logs/e2e-....jsonl",
  "exit_code": 0
}
```

### 7.4 Agent 排查约定

- 失败时最后有效诊断行为 `status=failed` 的 step 记录
- `run_summary.failed_step` 指向首个失败步骤
- `error.traceback` 仅 Python 侧异常填写；HTTP 错误填 `http.response_excerpt`
- 可选 `suggested_actions` 字符串数组（如 parse 超时 → 查 `logs/backend.log`）

## 8. Integration 模式

| 项 | Live | Integration |
|----|------|-------------|
| 服务 | `start.sh` | 不启动 |
| Client | HTTP | TestClient + `db_session` |
| 文件 | 真实 fixture 上传 | 同上或内存 UploadFile |
| 日志 | `logs/e2e-<run_id>.jsonl` | `logs/e2e-integration-<run_id>.jsonl` |
| 检索 | 真实索引 | 测试库需 seed 或跑完整 publish 建索引 |

实现方式：`integration` 模式在脚本内 `subprocess` 调用  
`pytest backend/tests/integration/test_e2e_pipeline_flow.py -q`  
或内嵌 TestClient（优先内嵌，避免双进程日志合并问题）。

新增测试文件：`backend/tests/integration/test_e2e_pipeline_flow.py` — 调用 `scripts/lib/e2e` 的 runner，`mode=integration`。

## 9. 检索断言

### 9.1 动态 query（`retrieval_dynamic`）

1. 取 `auto_publish` 第一条的 `title`
2. 截取 ≥2 字的子串作为 `query`（去标点）
3. POST `/retrieval/search`，`intent=knowledge_lookup`，`top_k=10`
4. 断言：hits 中任一 `object_id` ∈ `published_object_ids`

### 9.2 冒烟 query（`retrieval_smoke`）

- 固定 query：`技术方案`
- 断言：`len(hits) >= 1`（不强制 object_id 匹配，验证索引非空）

两步骤均写 `assertion` 字段；失败 `status=failed`。

## 10. 错误处理

- **Fail-fast**：任一步 `failed` 后跳过后续业务步骤，仍写 `run_summary`（`exit_code=1`）
- **HTTP 4xx/5xx**：记 `http` 块，`error.type=HTTPError`
- **Poll 超时**：默认 600s（与 epic3 `POLL_MAX` 一致），可 `--poll-max` 覆盖
- **Teardown**：默认 Live 模式调用 `scripts/stop.sh`；`--keep-services` 跳过

## 11. 测试与验收

| 验收项 | 命令 |
|--------|------|
| Live actual_bid | `python scripts/e2e_pipeline_test.py --purpose actual_bid --kb-id <id> --file backend/tests/fixtures/sample-actual-bid.docx` |
| Live template | `python scripts/e2e_pipeline_test.py --purpose template_file --kb-id <id> --file backend/tests/fixtures/sample-template.docx` |
| Integration | `python scripts/e2e_pipeline_test.py --mode integration --purpose actual_bid` |
| Agent 可读性 | 故意 `--kb-id` 无效 → jsonl 含 `preflight` failed + `http`/`error` |

成功标准：exit 0；jsonl 含完整 step 序列；`retrieval_dynamic` 与 `retrieval_smoke` 均为 `ok`。

## 12. 非目标（YAGNI）

- 不启动 frontend（`SKIP_FRONTEND=1`）
- 不覆盖 Epic 6 生成辅助链路
- 不生成 Markdown 报告
- 不支持批量多文件导入
- 不修改 Constitution 人工确认门生产行为（仅测试脚本 API 自动 confirm）

## 13. 后续实现

批准本设计后，使用 **writing-plans** 技能生成实现计划（任务拆分、TDD 顺序、文件清单）。
