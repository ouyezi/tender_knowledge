# Design: 铁建标书 E2E 验收（数据库重置 + 全链路 + 候选工作台）

**Date**: 2026-06-14  
**Status**: Approved (brainstorming)  
**Related scripts**: `scripts/e2e_pipeline_test.py`, `scripts/quickstart-epic4-dingxin-verify.sh`, `scripts/bootstrap-dingxin-candidates.py`  
**Test asset**: `/Users/tongqianni/xlab/标书助力/测试招投标文件/标书诊断/中铁/铁建福利商城-标书.docx` (~1.0 GB)

## 1. 背景与目标

平台 MVP 链路为：单文件导入 → 用途确认 → 解析 → 候选知识 → 人工确认发布 → 检索。
现有 E2E 脚本（`e2e_pipeline_test.py`）已贯通导入到检索，但：

- 无「仅清业务数据」的重置能力
- 检索断言仅 2 项（动态关键词 + 「技术方案」冒烟）
- Epic4 候选工作台场景（编辑/合并/批量/审计/隔离）仍在 bash 中，硬编码鼎信 import_id
- 未针对铁建 1GB 大文件调优 timeout

**目标**：交付可一键执行的验收入口，在本地 Live 环境对铁建标书跑通「重置 → 新建 KB → 导入 → 知识片段 → 完整检索 + 候选工作台」，并用 Integration 模式对小 fixture 做回归；问题仅通过 JSONL 记录。

## 2. Brainstorming 决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 数据库清空 | **B** — 仅清业务数据，保留 schema / 分类树配置 |
| D2 | 运行模式 | **C** — Live 跑铁建大文件 + Integration 跑小 fixture 回归 |
| D3 | 验收范围 | **C** — 完整检索 + Epic4 候选工作台场景 |
| D4 | 问题记录 | **A** — 仅 JSONL，不写 Markdown 报告 |
| D5 | 知识库 | **A** — 重置后自动新建 KB（clone 分类树） |

## 3. 实现路径对比

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **① 分层模块化（采用）** | `reset_business_data.py` + `e2e/steps/workbench.py` + `run_zhongtie_acceptance.py` | 重置可复用；Epic4 Python 化；与 E2E 解耦 | 新增 3–4 文件 |
| ② 单脚本扩展 | 在 `e2e_pipeline_test.py` 加 `--reset` / `--workbench` | 改动集中 | 脚本膨胀；铁建与通用 E2E 耦合 |
| ③ Bash 编排 | shell 串联 truncate + 现有脚本 + epic4 sh | 改动最小 | JSONL 不统一；hardcoded ID；难维护 |

## 4. 架构与入口

```text
run_zhongtie_acceptance.py
  ├─ Phase 0: reset_business_data (DB TRUNCATE + STORAGE_ROOT 清理)
  ├─ Phase 1: create_kb (POST /kbs, clone_from 含分类树的 seed KB)
  ├─ Phase 2: e2e_pipeline (Live, 铁建 docx, poll_max=7200)
  ├─ Phase 3: workbench_scenarios (Epic4 场景 0–9, Python 化)
  ├─ Phase 4: extended_retrieval (BM25/向量/分类过滤/trace)
  └─ Phase 5: integration_regression (sample-actual-bid.docx, mode=integration)
```

**主入口**：`scripts/run_zhongtie_acceptance.py`

```bash
.venv/bin/python scripts/run_zhongtie_acceptance.py \
  --file "/Users/tongqianni/xlab/标书助力/测试招投标文件/标书诊断/中铁/铁建福利商城-标书.docx" \
  --poll-max 7200 \
  --keep-services
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--file` | 铁建 docx 路径（见上） | Live 主链路测试文件 |
| `--poll-max` | `7200` | 解析轮询上限（秒），1GB 文件需 2h 级 |
| `--skip-reset` | false | 跳过重置（续跑/debug） |
| `--skip-integration` | false | 跳过 Integration 回归 |
| `--stop-after` | `candidates` | Phase 2 E2E 停在候选阶段（为 Phase 3 工作台留 pending）；设 `parse` 可更早暂停 debug |
| `--keep-services` | false | Live 结束后不 stop.sh |
| `--log-file` | `logs/zhongtie-<run_id>.jsonl` | JSONL 输出 |
| `--clone-from-kb-id` | auto | 指定 clone 源 KB；默认取第一个含 chapter_taxonomies 的 active KB |

**1GB 文件关键参数**：

- `poll_max_seconds`: 默认 **7200**（2 小时）
- LiveClient 上传 HTTP timeout: **1800s**
- 解析 poll interval: 保持 5s（可后续 `--poll-interval` 扩展）

**退出码**：`0` 全通过；`1` 业务/场景失败；`2` 环境/重置/建 KB 失败。

## 5. Phase 0 — 业务数据重置

### 5.1 保留（不 TRUNCATE）

- `knowledge_bases`
- `chapter_taxonomies`, `chapter_taxonomy_synonyms`, `chapter_taxonomy_bindings`
- `product_categories`, `product_category_aliases`
- `retrieval_strategy_versions`, `prompt_config_versions`

### 5.2 清空（TRUNCATE … RESTART IDENTITY CASCADE）

按 FK 依赖顺序执行（实现时以 SQLAlchemy `text()` 或单事务脚本）：

**导入域**：`file_imports`, `import_tasks`, `import_audit_logs`, `file_purpose_suggestions`

**文档域**：`documents`, `document_tree_nodes`, `document_media_assets`, `document_parse_suggestions`

**解析域**：`actual_bid_parse_tasks`, `actual_bid_audit_logs`, `bid_outline_structure_diffs`, `bid_outline_nodes`, `bid_outlines`

**候选/KU**：`candidate_confirm_audit_logs`, `candidate_knowledge_stubs`, `candidate_knowledges`, `knowledge_units`, `wikis`, `manual_assets`

**检索域**：`retrieval_feedbacks`, `retrieval_traces`, `retrieval_index_entries`, `retrieval_eval_cases`, `retrieval_eval_runs`, `retrieval_eval_sets`

**模板/生成域**：`template_audit_logs`, `template_structure_diffs`, `template_publish_snapshots`, `template_parse_suggestions`, `template_parse_tasks`, `template_materials`, `template_variables`, `template_rules`, `template_chapters`, `templates`, `template_libraries`, `generation_snapshots`, `generation_tasks`, `chapter_drafts`, `module_assembly_suggestions`, `downstream_task_entries`, `tender_requirement_contexts`, `chapter_pattern_mining_tasks`, `chapter_patterns`, `classification_audit_logs`, `kb_clone_logs`

### 5.3 文件存储

清空 `STORAGE_ROOT`（环境变量，默认 `backend/uploads/`）下所有文件，保留目录本身。

### 5.4 安全约束

`reset_business_data()` 仅在 `DATABASE_URL` host 为 `127.0.0.1` / `localhost` 且 port 为 `5433`（或 `TEST_DATABASE_URL` 显式覆盖为本地 SQLite integration 路径）时执行；否则 raise 并 exit 2。

**模块位置**：`scripts/lib/e2e/reset_business_data.py`

## 6. Phase 1 — 新建知识库

重置完成后调用 Live API：

```http
POST /api/v1/kbs
{"name": "铁建验收-<YYYYMMDD-HHMMSS>", "clone_from_kb_id": "<seed-kb-uuid>"}
```

- **seed KB 选择**：查询 DB 中第一个 `status=active` 且存在 `chapter_taxonomies` 记录的 KB
- 若无 seed KB：exit 2，JSONL 记录 `create_kb` 失败原因
- 将返回的 `kb_id` 写入 RunContext，供后续 Phase 使用

## 7. Phase 2 — Live E2E 主链路

复用 `E2EPipelineRunner` + `LiveClient`，配置：

- `purpose=actual_bid`
- `mode=live`
- `file_path` = 铁建 docx
- `kb_id` = Phase 1 新建 KB
- `poll_max_seconds` = CLI `--poll-max`（默认 7200）
- `auto_publish_count=1`（workbench 场景需更多 pending，pipeline 停在 candidates 或 publish 前由 Phase 3 接管）

**与现有 E2E 的分工**：

- Phase 2 默认 `--stop-after candidates`，保证 Phase 3 有足够 pending 候选（>= 3）
- Phase 2 内 `--auto-publish-count 0` 等效于仅生成候选

步骤序列：preflight → bootstrap_services → upload → confirm → parse → taxonomy_backfill → candidate_generate → list_candidates

## 8. Phase 3 — 候选工作台场景（Epic4 Python 化）

**模块位置**：`scripts/lib/e2e/steps/workbench.py`

每个场景独立函数，返回 `StepResult`，写入同一 JSONL logger。

| Step | 场景 | 断言 |
|------|------|------|
| `wb_pending_exists` | 0 pending 存在 | `GET candidates?status=pending` total >= 3 |
| `wb_filter_by_import` | 1 按 import_id 筛选 | 筛选命中 >= 1 |
| `wb_edit_candidate` | 2 编辑候选 | PATCH 后 status 仍 pending |
| `wb_publish_single` | 3 单条发布 KU | status=published, confirmed_object_id 非空 |
| `wb_ignore_candidate` | 4 忽略候选 | status=rejected |
| `wb_merge_candidates` | 5 合并候选 | merged_count=1 |
| `wb_batch_confirm` | 6 批量确认 | batch processed >= 1 |
| `wb_audit_log` | 7 审计日志 | actions 含 publish |
| `wb_retry_publish` | 8 发布失败重试 | retry → published；审计含 publish_failed |
| `wb_retrieval_isolation` | 9 检索隔离 | pending 候选 candidate_id 不在 published KU 列表 |

**依赖**：场景 3–9 需要 Phase 2 产出的 `import_id` 与足够 pending 候选；场景 5/6/8 在候选不足时 skip 并记 `status=skipped`（ok=true）。

## 9. Phase 4 — 扩展检索

**模块位置**：`scripts/lib/e2e/steps/common.py` 扩展（或 `retrieval_extended.py`）

| Step | 断言 |
|------|------|
| `retrieval_dynamic` | 发布标题关键词命中 published object_id（现有） |
| `retrieval_smoke` | query=「技术方案」, total >= 1（现有） |
| `retrieval_bm25_only` | enable_vector=false, enable_bm25=true, total >= 1 |
| `retrieval_category_filter` | 带 product_category_ids 过滤仍命中已发布 KU |
| `retrieval_trace` | return_options.include_trace=true 返回 trace_id |

Phase 4 在 Phase 3 的 `wb_publish_single` 之后执行（至少 1 条 published KU）。

## 10. Phase 5 — Integration 回归

调用现有 `run_integration_pipeline()`：

```python
PipelineConfig(
    purpose="actual_bid",
    file_path=ROOT / "backend/tests/fixtures/sample-actual-bid.docx",
    mode="integration",
    stop_after="retrieval",
    poll_max_seconds=30,
)
```

独立 JSONL 后缀 `-integration.jsonl` 或同一 log 文件用 `phase=integration` 字段区分。

## 11. 错误处理

| 情况 | 行为 |
|------|------|
| Phase 0/1 失败 | fail-fast, exit 2 |
| Phase 2 upload/parse 失败 | fail-fast, exit 1 |
| Phase 3 单场景失败 | 记录 JSONL `{ok:false}`, 继续后续独立场景 |
| Phase 4 检索失败 | 记录失败，继续 Phase 5（若未 skip） |
| 不可修复（OOM、LLM 不可用、1GB 超时） | JSONL `{error: {blocked: true, reason: "..."}}`, exit 1 |
| 最终 | JSONL 最后一行 `run_summary`: exit_code, phases_passed/failed, kb_id, import_id, log_file |

**修复策略（implementation 阶段）**：

- 可修复 bug：修代码后重跑失败 Phase（`--skip-reset --import-id <id> --from-step <step>`）
- 不可修复：仅 JSONL 留证，不生成 Markdown 报告

## 12. 新增/修改文件

| 文件 | 动作 |
|------|------|
| `scripts/run_zhongtie_acceptance.py` | 新增 — 统一入口 |
| `scripts/lib/e2e/reset_business_data.py` | 新增 — 业务数据重置 |
| `scripts/lib/e2e/steps/workbench.py` | 新增 — Epic4 场景 |
| `scripts/lib/e2e/steps/common.py` | 修改 — 扩展检索 step |
| `scripts/lib/e2e/client.py` | 修改 — 上传 timeout |
| `scripts/lib/e2e/types.py` | 修改 — PhaseConfig / 可选字段 |
| `scripts/e2e_pipeline_test.py` | 修改 — 暴露 poll-max 默认值文档 |
| `backend/tests/unit/test_reset_business_data.py` | 新增 — 安全约束 + 表清单单测 |
| `backend/tests/unit/test_workbench_steps.py` | 新增 — 场景 skip/断言逻辑单测 |

## 13. 测试计划

| 层级 | 内容 |
|------|------|
| Unit | reset 安全约束；workbench skip 逻辑；extended retrieval 断言 |
| Integration | `run_integration_pipeline` 回归（Phase 5） |
| Live manual | 铁建 1GB 全链路（需本地 Postgres + LLM + 2h 窗口） |

## 14. 非目标

- 不修改生产部署流程
- 不生成 Markdown 验收报告
- 不在本次实现 UI 自动化（Playwright）
- 不优化 1GB 文件解析性能本身（仅调 timeout；性能问题记 JSONL blocked）
