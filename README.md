# tender_knowledge

企业知识库平台（V3.0）需求与研发仓库。

## 文档

- [总需求](docs/总需求.md) — V3.0 完整产品需求
- [Epic 拆分](docs/epics/) — 按开发节奏拆分的分阶段需求

| Epic | 说明 |
|------|------|
| [epic0](docs/epics/epic0-分类底座.md) | 产品分类 + 章节分类底座 |
| [epic1](docs/epics/epic1-来源导入与文件分类确认.md) | 来源导入与文件分类确认 |
| [epic2](docs/epics/epic2-模板库解析与发布.md) | 模板库解析与发布 |
| [epic3](docs/epics/epic3-实际标书导入与候选知识.md) | 实际标书导入与候选知识 |
| [epic4](docs/epics/epic4-候选知识确认工作台.md) | 候选知识确认工作台 |
| [epic5](docs/epics/epic5-目录级检索与模块建议.md) | 目录级检索与模块建议 |
| [epic6](docs/epics/epic6-生成辅助升级.md) | 生成辅助升级 |

## 开发节奏

```text
Epic 0 分类底座
  → Epic 1 来源导入
  → Epic 2 模板解析 / Epic 3 实际标书导入（可并行）
  → Epic 4 候选知识确认
  → Epic 5 目录级检索
  → Epic 6 生成辅助升级
```

## E2E 验收脚本

对实际标书或模板文件跑通「导入 → 解析 → 自动发布 → 检索」全链路，输出 agent 可读的 JSONL 日志：

```bash
# Integration 模式（无需启动服务，CI 友好）
.venv/bin/python scripts/e2e_pipeline_test.py --mode integration --purpose actual_bid

# Live 全链路
.venv/bin/python scripts/e2e_pipeline_test.py \
  --purpose actual_bid \
  --kb-id <KB_UUID> \
  --file path/to.docx

# 重复文件：作为新版本上传
.venv/bin/python scripts/e2e_pipeline_test.py \
  --purpose actual_bid \
  --kb-id <KB_UUID> \
  --file path/to.docx \
  --duplicate-action new_version \
  --parent-import-id <EXISTING_IMPORT_UUID>

# 已 confirm / 已解析的 import 续跑（跳过 upload + confirm）
.venv/bin/python scripts/e2e_pipeline_test.py \
  --purpose actual_bid \
  --kb-id <KB_UUID> \
  --import-id <IMPORT_UUID> \
  --from-step candidates \
  --file path/to.docx
```

`--from-step` 可选：`auto` | `upload` | `confirm` | `parse` | `candidates` | `publish` | `retrieval`（非 `auto`/`upload` 时必须配合 `--import-id`）。仅指定 `--import-id` 且 `--from-step auto`（默认）时，脚本会根据 import / 解析 / 候选状态自动选择起始阶段。

**停在候选阶段（留给 UI 人工确认）**：

```bash
# 方式 1：显式停在候选列表之后
.venv/bin/python scripts/e2e_pipeline_test.py \
  --purpose actual_bid \
  --kb-id <KB_UUID> \
  --file path/to.docx \
  --stop-after candidates \
  --keep-services

# 方式 2：不自动发布（等价于跳过 publish + retrieval）
.venv/bin/python scripts/e2e_pipeline_test.py \
  --purpose actual_bid \
  --kb-id <KB_UUID> \
  --file path/to.docx \
  --auto-publish-count 0 \
  --keep-services
```

`--stop-after` 可选：`candidates` | `publish` | `retrieval`（默认 `retrieval` 跑全链路）。`--auto-publish-count 0` 会强制在候选阶段结束，即使未指定 `--stop-after`。

### E2E 与候选中心 UI 状态对照

| 脚本行为 | 后端候选状态 | UI「候选知识」筛选项 |
|----------|--------------|----------------------|
| 解析 + 候选生成后停止 | `pending` | **待处理**（标书/document 渠道） |
| 模板解析产生 stub | `pending_confirm` | **待确认**（模板/template 渠道） |
| 默认全链路 `auto_publish` | `published` | 筛选项暂无「已发布」；检索可命中 |
| （无） | `confirmed` | **已确认** — E2E 不会停留在此状态 |

标书 E2E（`--purpose actual_bid`）不会创建模板库；模板库需 `--purpose template_file`。

日志输出：`logs/e2e-<run_id>.jsonl`（或 `logs/e2e-integration-<run_id>.jsonl`）。

设计文档：`docs/superpowers/specs/2026-06-14-e2e-import-retrieval-pipeline-design.md`
