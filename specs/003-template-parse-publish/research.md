# Research: Epic 2 模板库解析与发布

**Date**: 2026-06-12  
**Feature**: `specs/003-template-parse-publish`

## R1 — docx 标题结构解析

### Decision

采用 **python-docx** 读取 Word 段落；按 `paragraph.style.name` 匹配 `Heading 1`–`Heading 9`
（及中文样式别名 `标题 1` 等）构建章节树；无 Heading 样式时降级为 **字号/加粗启发式**
+ 前缀数字编号（`1.`、`1.1`、`第一章`）推断 level 与 `sort_order`。

### Rationale

- MVP 主路径为 docx 模板；python-docx 成熟、无 LibreOffice 依赖，适合 Docker。
- 前缀数字排序对齐 spec FR-002 与 epic「前缀数字用于章节排序」。
- 无清晰层级时生成扁平树 + `needs_manual_review=true`，满足 Edge Case。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| LibreOffice headless 转 HTML 再解析 | 容器镜像大、运维复杂 |
| 纯 LLM 抽目录 | 延迟高、不可重复、难单测 |
| mammoth → markdown | 丢 level 信息，需二次启发式 |

---

## R2 — 内容块 → Template Material / Candidate

### Decision

在 docx 解析 walker 中，按 **当前 Heading 栈** 归属内容：

| 块类型 | 检测 | 输出 |
|--------|------|------|
| 固定段落 | 非 Heading 的普通段落 | `fixed_paragraph` material |
| 表格 | `paragraph._element` 同级 table | `table` / `excel_table` material |
| 图片 | inline shape / drawing | `image` material（存 storage 引用或 inline hash） |
| 可提取知识 | 段落长度 > 阈值且无占位符 | `candidate_knowledge_stub`（pending_confirm） |

PPT/封面/攻略/Excel **独立导入** 走 Epic 1 `template_material_ingest`；本 Epic 解析
路径对 docx 内嵌对象仅元数据 + 附件引用。

### Rationale

- 对齐总需求 §6.9 与 spec FR-003/FR-011。
- Candidate 与 Material 分离：Material 留在模板域；KU/Wiki 候选交给 Epic 4。

---

## R3 — 模板解析任务编排

### Decision

**双入口、单任务表**：

1. **自动**：Epic 1 确认后 `downstream_task_entries.task_type=template_file_parse`；
   `template_parse_runner` 轮询/BackgroundTasks claim `pending` → 创建 `template_parse_task`
   → 执行解析。
2. **手动**：`POST .../templates/parse` 指定 `import_id`（须已确认 template_file）。

任务状态：`pending → running → parse_ready（待人工确认）→ confirmed → failed`。
确认后 Template 状态 `draft`；发布后为 `published`。

失败时：更新 `template_parse_task.status=failed` + `error_message`；**不修改**
`file_imports` 记录；downstream entry 可 `failed` 或保留 `pending` 供 retry。

### Rationale

- 复用 Epic 1 downstream 契约（quickstart 场景 2 已验证占位）。
- 独立 `template_parse_tasks` 表便于任务日志、重试与 SC-003。
- `parse_ready` 显式表达人工确认门（G3）。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 复用 import_tasks 表 | task_type 膨胀；模板解析日志字段不同 |
| 解析完直接 published | 违反人工确认门 |

---

## R4 — 机器建议与人工确认分离

### Decision

解析产出写入 **`template_parse_suggestions`**（JSON 快照：建议 library、categories、
chapter 树、material 列表、ignore/extract 默认）+ **draft 实体**（`status=draft`,
`confirmed=false`）。

人工确认 API 一次性提交：

- library 归类（含 `template_library_id=null` 表示未归类）
- 章节树修正（层级/类型/产品分类/required/ignore）
- material 与 candidate 提取意向

确认后：`confirmed=true`，`structure_locked_at` 写入 Template；suggestion 归档只读。

### Rationale

- 对齐 Epic 1 `file_purpose_suggestions` 模式与 constitution G3。
- draft 实体使确认前可预览树编辑器；确认后正式可用。

---

## R5 — 重解析与待确认差异

### Decision

Template 已 `structure_locked_at` 非空时，再次解析：

1. 新解析结果写入 `template_structure_diffs`（`status=pending_review`）。
2. **不修改**已确认章节树；diff 含 added/removed/changed 节点摘要。
3. 管理员在确认界面 merge/reject diff 后应用。

未锁定（首次或仅 draft 未确认）可直接覆盖 draft 树。

### Rationale

- 落实 spec FR-007 与 constitution「人工修正后不得直接覆盖」。
- diff 表比版本分支简单，满足 MVP。

---

## R6 — Template Library 与「未归类」

### Decision

- `templates.template_library_id` **nullable**；null 表示「未归类模板」。
- Template Library 手工创建；**禁止**从目录/文件夹批量生成。
- Library 与 Template 均有独立 `status`：`draft | reviewing | published | deprecated`。
- **发布门控**：仅 `template_libraries.status=published` 参与 Epic 5 推荐查询；
  Template 发布可单独或随 Library 批量发布（MVP：Library publish 级联其下 draft Template）。

### Rationale

- 对齐 spec FR-008/FR-009/FR-014 与总需求 §6.4。
- nullable FK 比 sentinel UUID 更简单。

---

## R7 — 发布与版本管理

### Decision

发布时：

1. 校验 required 规则、必填变量默认值、章节树非空。
2. 递增 `version`（语义字符串 `major.minor`，MVP 仅 patch +1）。
3. 写入 `template_publish_snapshots`（JSON：library + templates + chapters + materials +
   variables + rules）供历史查看。
4. 更新 `status=published`；旧 published 版本标记 `superseded` 或保留多版本只读。

废弃：`status=deprecated`；禁止物理 DELETE。

### Rationale

- 满足 FR-014/FR-015/FR-016 与 constitution 数据生命周期。
- 快照表简化「查看历史版本」无需 temporal 表。

---

## R8 — Template Variable MVP

### Decision

- 解析阶段用正则 `\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}` 扫描段落/标题，自动创建
  `template_variables` 草稿。
- `value_type` MVP 固定 `string`；支持 `default_value`、`required`。
- 不支持表达式、脚本、嵌套。

### Rationale

- 对齐总需求 §6.7 与 spec FR-012。
- 正则足够覆盖 `{{project_name}}` 类占位符。

---

## R9 — Template Rule MVP

### Decision

| rule_type | MVP 行为 |
|-----------|----------|
| required | 章节 `required=true`；发布校验树中存在 |
| optional | 章节 `required=false` |
| product_match | `condition.field=product_category`，`operator=in`，绑定章节在指定分类下启用 |

`conditional`、`mutex`、`asset_required` 枚举预留，API 拒绝创建。

### Rationale

- 对齐 spec FR-013 与总需求 §6.6/§6.8。

---

## R10 — Candidate Knowledge 占位

### Decision

新增 **`candidate_knowledge_stubs`** 表（Epic 4 扩展或迁移）：

| 字段 | 说明 |
|------|------|
| stub_id | PK |
| kb_id, import_id, template_id, template_chapter_id | 溯源 |
| candidate_type | ku \| wiki |
| title, summary, content_preview | 提取片段 |
| product_category_ids, chapter_taxonomy_id | 建议分类 |
| status | pending_confirm \| confirmed \| rejected |
| epic4_batch_id | nullable，Epic 4 认领后写入 |

Epic 2 只创建 `pending_confirm`；Epic 4 工作台消费。

### Rationale

- G2/G3：候选与正式资产分离；Epic 2 不实现 Candidate 工作台 UI。

---

## R11 — 分类引用与审计

### Decision

- 确认/发布时写入 `classification_reference`，`object_type` 扩展：
  `template_library | template | template_chapter | template_material`。
- 新增 `template_audit_logs`：`parse_start`, `parse_complete`, `parse_fail`, `confirm`,
  `chapter_update`, `publish`, `deprecate`；含 `trace_id`、`operator_id`、`payload_summary`。

复用 Epic 0 `AuditMiddleware` 注入 `X-Trace-Id`。

### Rationale

- G4 全链路追溯；与 Epic 1 import_audit 模式一致。

---

## R12 — 对外只读查询（Epic 5 前置）

### Decision

提供 **internal/public read API**（同 KB 隔离）：

- `GET .../template-libraries?status=published` — 推荐候选库
- `GET .../templates/{id}/chapters/tree?status=published`
- `GET .../template-materials?template_id=&status=published`

未发布/未确认返回 404 或空集（implement 时统一为 **空集**，避免泄露 draft 存在性）。

### Rationale

- G5：为 Epic 5 模块建议预留契约；本 Epic 不实现推荐算法。

---

## R13 — LLM 环境配置与降级

### Decision

- 配置项（`.env` / 环境变量）：`LLM_PROVIDER`（预设 `qwen` | `openai`）、
  `LLM_API_KEY`、`LLM_BASE_URL`（可选覆盖）、`LLM_MODEL`（可选覆盖）、
  `LLM_MAX_CHUNK_CHARS`（默认 8000）、`LLM_REQUEST_TIMEOUT_SEC`（默认 60）。
- 实现：`src/config.py` provider 预设 + `src/services/llm_client.py` OpenAI 兼容
  `/chat/completions`；无 `LLM_API_KEY` 或 HTTP/解析失败 → 返回 `None`，调用方降级规则。
- 默认千问：`https://dashscope.aliyuncs.com/compatible-mode/v1` + `qwen-plus`。

### Rationale

- 对齐 spec FR-021/FR-023 与 Epic 1 `purpose_suggestion` 可选 LLM 模式。
- 环境变量切换 provider，无需改代码或重新部署镜像（仅改 `.env`）。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 硬编码 provider SDK | 切换成本高；与 Constitution「LLM 辅助、人工确认」解耦不够 |
| 整文件送 LLM | 违反澄清 SC-008；大标书/资质合集不可行 |

---

## R14 — 知识块级分类（非文件级）

### Decision

**分类粒度**定义：

| 层级 | 对象 | 分类维度 | 说明 |
|------|------|----------|------|
| 文件级 | File Import | `file_purpose` only | Epic 1 已确认；Epic 2 不重复细分 |
| 知识块级 | Template Chapter | chapter_taxonomy, product_category | 每章节节点独立建议 |
| 知识块级 | Template Material | product_category, material_type | 每素材片段独立建议 |
| 知识块级 | Candidate Knowledge Stub | product_category, chapter_taxonomy, knowledge_type | 每候选独立建议 |

导入文件可能是完整标书、标书模板、产品方案、资质合集；**不对文件做细粒度小分类**，
仅在解析产出知识块后执行分类建议。人工确认界面以 **块** 为粒度展示与修正（spec FR-004a）。

分类流水线：

1. **规则优先**：文件名关键词、标题样式、Epic 0 别名表 → 块级初始建议。
2. **LLM 增强**（可选）：对单块 `title + content_preview` 调用 `chunk_classification_service`。
3. **合并**：LLM 可用且置信度更高时标记 `suggestion_source=llm|hybrid`；否则 `rule`。

### Rationale

- 对齐 2026-06-12 澄清：文件类型多样，块级分类才能支撑混合文档（如完整标书内含多产品章节）。
- 与 G2「知识资产优先」一致：分类绑定可治理的知识块，而非原始文件。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 文件级 product_category 继承到所有块 | 无法处理混合文档；与澄清冲突 |
| 仅 LLM 分类 | 无 Key 时不可用；违反 FR-023 |

---

## R15 — 大文件分批 LLM 处理

### Decision

解析流水线 **两阶段**：

```text
Phase A（结构，无 LLM）
  docx_outline_parser → 章节树
  docx_content_extractor → materials + candidate 候选块

Phase B（分类，按块批处理）
  FOR each KnowledgeChunk in chunks:
    IF len(chunk.text) > LLM_MAX_CHUNK_CHARS → truncate_for_llm
    chunk_classification_service.classify(chunk)  # 单块一次 LLM
    UPDATE llm_progress on template_parse_task
  NEVER: read entire docx text into one LLM prompt
```

- `template_parse_tasks.llm_progress` JSON：
  `{ "total_chunks", "completed_chunks", "failed_chunks", "degraded_to_rule", "batch_size": 1 }`。
- 大文件（>50MB 或 >200 页）：Phase A 完成后即可部分写入 suggestion（章节树先可见）；
  Phase B 异步补全块级分类；`parse_ready` 在 Phase A+B 均完成或 Phase B 全部降级后触发。
- SC-008：首批可确认知识块 = Phase A 完成时间；不因整文件 LLM OOM/超时失败。

### Rationale

- 对齐 spec FR-022、Edge Case 超大文档、SC-008。
- research R1 已拒绝「纯 LLM 抽目录」；本决议将 LLM 限定在块级分类/摘要。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 整文件摘要后分类 | 上下文超限；延迟与成本不可控 |
| Map-Reduce 多轮 LLM 合并 | MVP 复杂度过高；块级独立分类已满足确认工作台 |
