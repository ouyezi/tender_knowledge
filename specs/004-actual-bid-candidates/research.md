# Research: Epic 3 实际标书导入与候选知识

**Date**: 2026-06-12  
**Feature**: `specs/004-actual-bid-candidates`

## R1 — docx 全文结构解析（Document Tree）

### Decision

复用 Epic 2 的 **python-docx** 解析栈：`docx_outline_parser.parse_outline` 生成标题树；
新增 `docx_document_walker` 按 Heading 栈归属段落/表格/图片为 **内容块**，写入
`document_tree_nodes`（`node_type=heading|paragraph|table|image`）。

Document Tree 表示**全文结构**（含正文块）；Bid Outline 仅抽取目录级标题节点。

### Rationale

- 与 Epic 2 共享单测与 fixtures 策略，降低维护成本。
- 总需求 §6.12 明确 Document Tree 与 Bid Outline 双轨；全文 walker 支撑 KU 候选内容提取。
- 无清晰层级时扁平树 + `needs_manual_review=true`，不失败。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| Bid Outline 即 Document Tree | 违反双轨模型；编辑目录会污染正文追溯 |
| 仅存 Bid Outline 不存全文树 | KU 来源链无法落到 Document Tree Node |

---

## R2 — Bid Outline 抽取优先级（内置目录 → 样式/编号）

### Decision

**两阶段抽取**：

1. **内置目录优先**：用 `lxml` 解析 `word/document.xml` + `word/styles.xml`，检测 TOC
   字段（`w:instrText` 含 `TOC`）及 `w:sdt` 目录内容；若存在有效 TOC 条目，以其
   为 Bid Outline 初稿。
2. **降级**：复用 `docx_outline_parser`（Heading 样式 + 数字编号启发式），与 Epic 2
   一致。

抽取结果写入 `bid_outlines` + `bid_outline_nodes`；每个节点 `source_node_id` 指向
对应 `document_tree_nodes.node_id`（标题节点）。

### Rationale

- 对齐 spec FR-006 与 epic「优先内置目录」。
- python-docx 不直接暴露 TOC；lxml 轻量、已在 Epic 2 依赖中。
- 无 TOC 时行为与模板解析一致，可单测。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅 Heading 样式 | 不满足「内置目录优先」 |
| LibreOffice 导出书签 | 运维重 |
| LLM 抽目录 | 不可重复、难审计 |

---

## R3 — Document Tree 与 Bid Outline 编辑隔离

### Decision

- **独立表**：`documents`、`document_tree_nodes`、`bid_outlines`、`bid_outline_nodes`。
- Bid Outline 编辑 API **仅写** `bid_outline_nodes`；Document Tree 编辑 API（MVP 只读
  或有限 PATCH 分类字段）**不反向同步** Bid Outline。
- 重解析产生新 Document Tree 版本时，对比既有 `bid_outline_nodes` 生成
  `bid_outline_structure_diff`（同 Epic 2 `template_structure_diff` 模式）；人工 apply
  后才合并。

`bid_outlines.structure_locked_at` 在管理员「确认目录」后写入；锁定后重解析仅 diff。

### Rationale

- 直接落实总需求 §6.12 与 Constitution G3/G4。
- 复用 Epic 2 已验证的 diff 人工门模式。

---

## R4 — 候选知识数据模型（Document 来源）

### Decision

新增 canonical 表 **`candidate_knowledges`**（对齐总需求 §6.15），字段含
`source_doc_id`、`source_node_id`、`candidate_type`、`status=pending` 等。

Epic 2 的 `candidate_knowledge_stubs`（模板来源）**保留**；本 Epic 列表 API **聚合**
两表（`source_channel: document | template`），Epic 4 统一工作台再收敛。

Document 路径候选 **禁止** 写入 `candidate_knowledge_stubs`（避免 nullable FK 膨胀）。

### Rationale

- 总需求模型以 Document Tree Node 为 KU 来源追溯锚点（§6.12）。
- 模板 stub 已上线；大 refactor 风险高，聚合 API 为 MVP 务实路径。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 扩展 stub  nullable template_id | 单表多态复杂、Epic 2 迁移风险 |
| 仅内存候选不落库 | 违反 FR-014 追溯与 Epic 4 消费 |

---

## R5 — 下游任务编排（actual_bid 三件套）

### Decision

**串行流水线**（单 runner `actual_bid_parse_runner`）：

```text
claim document_parse
  → 解析 docx → documents + document_tree_nodes
  → mark document_parse completed
claim bid_outline_extract
  → bid_outlines + bid_outline_nodes (+ 块级分类建议)
  → mark bid_outline_extract completed
claim candidate_knowledge_generate
  → candidate_knowledges (pending) + 可选 chapter_pattern 种子数据
  → mark candidate_knowledge_generate completed
```

- 手动重试：`POST .../actual-bid-parse/trigger` 同 Epic 2 template parse。
- `chapter_pattern_mining`：**独立任务**，按 `kb_id` 批量挖掘，不挂在单文件 downstream 链上。

失败策略：更新对应 `actual_bid_parse_tasks` + downstream entry `failed`；**不删除**
`file_imports` / `documents`。

### Rationale

- Epic 1 已写入三条 downstream 类型（integration test 已覆盖）。
- 串行保证 outline 依赖 tree、candidate 依赖 taxonomy 映射建议。

---

## R6 — 章节类型 → 候选知识类型规则

### Decision

**规则引擎 MVP**（`chapter_candidate_rules.py`），输入 `chapter_taxonomy_id` /
taxonomy code：

| Taxonomy 族（Epic 0 code 前缀或映射表） | candidate_type | suggested_knowledge_type |
|----------------------------------------|----------------|--------------------------|
| 技术方案 | ku | solution |
| 产品功能 | ku | product_capability |
| 供应链 | ku | capability / solution |
| 企业实力/资质/荣誉 | ku | qualification |
| 稳定通用段落（规则：重复率高 + 无项目专有实体） | wiki | general |

规则表放 `backend/src/config/chapter_candidate_rules.yaml` 或 DB 种子；LLM 仅辅助
`summary` 与边界 case，失败降级规则。

### Rationale

- 对齐 epic「Candidate Knowledge 生成规则」与 spec FR-012。
- 与 Epic 2 `chunk_classification_service` 同模式（规则优先 + 可选 LLM）。

---

## R7 — LLM 与大文件策略

### Decision

**完全复用** Epic 2 基础设施：

- 环境变量：`LLM_PROVIDER`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`LLM_MAX_CHUNK_CHARS`
- `llm_client.py` + 按 **章节/段落块** 分批调用
- 无 Key 或失败 → 规则降级，**不阻断**解析主流程
- `actual_bid_parse_tasks.llm_progress` 记录块级进度

### Rationale

- Constitution 与 Epic 2 澄清结论一致；避免双套配置。
- spec FR-023 大文件分批与 SC-001 时间目标。

---

## R8 — Chapter Pattern 候选挖掘（MVP）

### Decision

**离线批任务** `chapter_pattern_mining`：

1. 输入：`kb_id` 下 `status in (draft, confirmed)` 的 `bid_outline_nodes` +
   已发布 `template_chapters`（Epic 2）。
2. 按 `chapter_taxonomy_id` + 归一化标题（去编号/空格）聚类。
3. 频次 ≥ 2 的簇生成 `chapter_patterns`（`status=candidate`），记录
   `source_outline_ids`、`source_template_chapter_ids`、`frequency`。

MVP **不用 LLM** 归纳；pattern_name 取众数标题。增强阶段可加 LLM 命名。

### Rationale

- Epic 3 P3 优先级；规则聚类可测、可解释。
- 对齐总需求 §6.13 `status=candidate`。

---

## R9 — 管理后台 UI 范围

### Decision

新增 **目录中心** `OutlineCenter`（`/outlines`）：

- Bid Outline 列表 / 树编辑 / 章节分类映射
- 解析任务日志 Tab（过滤 `actual_bid_parse_tasks`）

**候选知识中心** `CandidateCenter`（`/candidates`）**只读列表**：

- 筛选 `status=pending`；展示来源链摘要
- **无**确认/合并/发布按钮（Epic 4）

### Rationale

- 对齐 spec US-6、FR-018/FR-019。
- 与 TemplateLibraryCenter 并列，复用 Ant Design Tree/ProTable 模式。

---

## R10 — 检索隔离（未确认候选）

### Decision

- `candidate_knowledges` 与 `candidate_knowledge_stubs` **不注册**到 Epic 5 检索索引。
- 对外查询 API（若存在占位）MUST 过滤 `status=pending` / `pending_confirm`。
- 本 Epic 仅实现列表只读 API，不实现检索。

### Rationale

- Constitution G2/G3 与 spec FR-015、SC-006。
