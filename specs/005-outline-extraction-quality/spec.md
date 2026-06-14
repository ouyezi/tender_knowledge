# Feature Specification: 标书目录提取质量增强

**Feature Branch**: `005-outline-extraction-quality`

**Created**: 2026-06-14

**Status**: Ready for unified acceptance with Epic 3 (004)

**Input**: User description: "借鉴 tender_doctor 目录提取方式，增强 tender_knowledge 标书目录抽取质量：过滤误识别标题、输出质量指标、统一层级推断与建树逻辑，改善鼎信等实际标书的目录可用性。"

**Source**: `docs/superpowers/specs/2026-06-14-outline-hierarchy-inference-design.md` · `specs/004-actual-bid-candidates/spec.md`（US-2、FR-006）· tender_doctor 提取流水线调研（2026-06-14）

**Related Epic**: Epic 3 实际标书导入与候选知识（目录抽取子能力增强，非新 Epic）

## 背景与问题陈述

在 `content_heuristic` 层级推断上线并修复 `parent_id` 落库问题后，鼎信餐补标书等文档已能生成多级目录树，但仍存在两类突出问题：

1. **误识别噪声**：正文中的列举编号（如「1. 根据贵方…」）、日期行、参选函条目等被识别为一级标题，导致目录臃肿、难以人工确认。
2. **质量不可见**：解析完成后，管理员无法快速判断目录是否「过扁、孤儿过多、待复核过多」，只能逐条打开确认向导或目录详情排查。

参考项目 `tender_doctor` 的做法表明：在规则 baseline 之上，通过 **structural_only（纯结构节点）** 区分、**heading 栈建树**、**解析质量评估** 可显著改善目录可用性，且无需引入 LLM 即可覆盖 MVP 场景。

本特性在保留现有三级降级策略（内置 TOC → 规则启发式 → flat_fallback）与人工作确认闸门的前提下，提升目录抽取的**准确性、可解释性与可运维性**。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 过滤非章节性「伪标题」 (Priority: P1)

知识库管理员上传一份以中文编号为主、无标准 Word Heading 样式的实际标书（如鼎信餐补标书）并完成解析后，希望系统在生成 Bid Outline 时自动区分「真章节标题」与「正文列举/日期/封面信息」，避免目录被大量噪声节点淹没。

**Why this priority**: 误识别直接决定目录是否可用；是管理员进入确认向导前的第一道质量门槛，影响 Epic 3 核心体验。

**Independent Test**: 使用鼎信餐补标书（或等价 fixture）触发解析；对比增强前后 Bid Outline 节点数与 L1 占比；确认参选函正文列举项不再作为独立一级章节出现在默认目录中，且真章节（如「一、报价表格式」「二、参选响应函」）仍保留。

**Acceptance Scenarios**:

1. **Given** 段落被识别为标题但去除标题文本后**无实质正文**（纯结构/目录行），**When** 目录抽取完成，**Then** 该节点标记为「纯结构节点」，默认**不进入** Bid Outline，或进入时标记为需人工复核且排序靠后（见 Assumptions）。
2. **Given** 段落匹配正文列举模式（如以「1.」「2.」开头的长句承诺/声明，且位于已知父章节「参选响应函」之下），**When** 目录抽取完成，**Then** 系统将其**收纳为父章节正文**而非独立 Bid Outline 节点。
3. **Given** 段落为日期、签章、页眉页脚类短文本（如「2026 年 5 月 19 日」），**When** 目录抽取完成，**Then** 该段落**不得**成为 Bid Outline 根节点。
4. **Given** 文档含 Word 内置 TOC（`toc1`/`toc2`）条目，**When** 目录抽取完成，**Then** TOC 策略优先级不变，TOC 条目不受本特性过滤规则降级。
5. **Given** 某节点被过滤或降级，**When** 管理员查看解析建议或 Document Tree，**Then** 仍可追溯到原始段落及过滤原因（可解释性）。

---

### User Story 2 - 解析完成后展示目录质量指标 (Priority: P1)

知识库管理员在实际标书解析任务进入「待确认」状态后，希望在目录中心或确认向导入口一眼看到目录质量摘要（如层级深度、L1 占比、待复核比例），以便决定是否需要优先人工整理。

**Why this priority**: 质量可见性降低排查成本；与 tender_doctor 的 layout quality 思路一致，支撑人工确认闸门（Constitution III）。

**Independent Test**: 完成一份标书解析后，在待确认任务或目录详情中查看质量摘要；对已知「过扁」与「结构良好」的两份样例，摘要指标应能区分二者。

**Acceptance Scenarios**:

1. **Given** 实际标书解析任务状态为 `ready` 且关联 Bid Outline 已生成，**When** 管理员查看该任务或目录列表，**Then** 展示目录质量摘要，至少包含：节点总数、最大层级深度、L1 节点占比、标记待复核节点数。
2. **Given** 目录质量摘要显示 L1 占比超过约定阈值（见 Assumptions），**When** 管理员打开确认向导，**Then** 系统展示醒目提示，建议优先检查目录结构。
3. **Given** 解析策略为 `flat_fallback`，**When** 展示质量摘要，**Then** 明确标注「扁平降级」及建议人工重建层级。
4. **Given** 解析策略为 `toc` 或 `content_heuristic` 且质量指标正常，**When** 展示质量摘要，**Then** 不展示误导性错误提示。

---

### User Story 3 - Document Tree 与 Bid Outline 层级一致且父子关系正确 (Priority: P2)

知识库管理员在目录详情页查看树形结构时，期望所见层级与数据库中 `level` 字段一致，父子缩进正确，不因落库或前端建树逻辑导致「全部显示为 L1」。

**Why this priority**: 已在 2026-06-14 修复 `parent_id` 落库 bug；本故事将「正确落库」固化为可回归的规格要求，并扩展到 walk 与 extract 共用推断结果。

**Independent Test**: 对含三级以上中文编号的标书解析后，目录详情树形视图中应出现 L2/L3 嵌套；API 返回的 `parent_id` 与树展示一致。

**Acceptance Scenarios**:

1. **Given** 层级推断识别出父子关系，**When** Bid Outline 持久化完成，**Then** 不少于 70% 的非根节点具备非空 `parent_id`（对含真实层级结构的样例文档）。
2. **Given** Bid Outline 节点已持久化，**When** 管理员打开目录详情树形视图，**Then** 子节点在父节点下缩进展示，层级标签（如 L1/L2）与节点 `level` 一致。
3. **Given** 同一文档的 Document Tree 与 Bid Outline 均由一次解析产生，**When** 比对章节标题与层级，**Then** 二者在章节级节点上无系统性层级冲突（允许 Bid Outline 为 Document Tree 的子集）。

---

### User Story 4 - 统一层级推断源，避免双路径不一致 (Priority: P2)

系统开发/运维人员希望 `walk_document`（Document Tree）与 `extract_toc_entries`（Bid Outline）共用同一份层级推断结果，避免一条路径识别为章节而另一条路径遗漏或层级不同。

**Why this priority**: tender_doctor 通过 Block → chunk → section_tree 单一事实来源避免不一致；tender_knowledge 当前两条路径需收敛以降低维护成本与隐蔽 bug。

**Independent Test**: 对同一 docx 样例分别检查 walk 输出的 outline 节点集合与 extract 输出的 toc 条目集合；章节标题与 level 应一一对应（允许 extract 为 walk 的子集因过滤规则）。

**Acceptance Scenarios**:

1. **Given** 单次实际标书解析任务，**When** Document Tree 与 Bid Outline 生成完成，**Then** 二者来自同一推断结果快照（可追溯至同一 `infer_result` 或等效产物）。
2. **Given** 内置 TOC 策略命中，**When** 生成 Bid Outline，**Then** Document Tree 的章节节点与 TOC 条目在标题与层级上保持一致。

---

### Edge Cases

- 文档仅有封面与目录页、几乎无正文：纯结构节点占比极高，系统应提示「结构为主文档」而非输出数百 L1 节点。
- 文档同时使用 Word Heading 与中文编号：Heading 样式优先，中文规则不覆盖高置信度样式命中。
- 参选函中「1.」「2.」短条目与「1.1」「1.1.1」真子章节并存：数字编号深度与上下文（父章节、正文长度）共同决定，避免一刀切。
- 重解析（`force_reparse`）且目录已锁定：过滤与质量指标仅作用于新生成差异或草稿节点，不破坏 Constitution 要求的差异确认流程。
- 超大文档（>200MB docm）：质量指标计算不得显著延长解析总时长（见 Success Criteria）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在目录抽取流水线中识别「纯结构节点」（段落作为标题候选但无实质正文），并记录 `structural_only` 或等效标记。
- **FR-002**: 系统 MUST 提供可配置的规则集，将以下模式从默认 Bid Outline 中排除或降级为待复核：日期行、正文长句列举编号、已知父章节下的承诺条目列表。
- **FR-003**: 系统 MUST 在排除或降级节点时记录**过滤原因码**（如 `body_list_item`、`date_line`、`structural_only`），供解析日志与人工排查使用。
- **FR-004**: 系统 MUST 在实际标书解析任务完成（`ready`）时计算并持久化目录质量摘要，至少包含：`node_count`、`max_depth`、`l1_ratio`、`needs_manual_review_count`、`extract_strategy`。
- **FR-005**: 系统 MUST 在 L1 占比或待复核占比超过约定阈值时，向管理员展示警告提示（目录中心或确认向导入口）。
- **FR-006**: 系统 MUST 保证 Bid Outline 持久化时 `parent_id` 与 `level` 一致；非根节点的父子关系可通过 `parent_id` 完整复原树形结构。
- **FR-007**: 系统 MUST 使单次解析内的 Document Tree 章节推断与 Bid Outline 抽取基于同一层级推断产物，避免独立重复推断。
- **FR-008**: 系统 MUST 保持现有策略优先级：内置 TOC > 规则启发式（含中文编号/Markdown）> flat_fallback；本特性不得降低 TOC 命中率。
- **FR-009**: 被过滤节点 MUST 保留于 Document Tree 并可追溯原因；确认向导 MUST 以只读方式展示过滤摘要（条数 + 样本列表），MVP **不要求**向导内一键恢复进 Bid Outline。
- **FR-010**: 系统 MUST 将质量摘要与过滤统计写入解析任务进度/建议载荷，供前端只读展示（不要求本特性实现完整前端 redesign）。
- **FR-011**: 系统 MUST 为鼎信餐补标书（或登记的代表性 fixture）提供回归基准：增强后 Bid Outline 节点数较增强前减少不少于 30%，且不少于 10 个已知真章节标题仍保留。
- **FR-012**: 失败或部分失败的解析任务 MUST NOT 出现在「待确认」列表（`ready` 且可进入确认向导）；与既有 P0 修复行为保持一致。

### Key Entities

- **OutlineQualitySummary**: 单次解析产出的目录质量摘要；关联 `parse_task_id` 与 `bid_outline_id`；含节点统计、层级分布、策略与警告标志。
- **HeadingFilterDecision**: 对单个标题候选的处置结果；含 `action`（keep / demote / exclude）、`reason_code`、`source_block_ref`。
- **StructuralNodeFlag**: 标记节点是否为纯结构/目录行；影响是否进入默认 Bid Outline。
- **BidOutlineNode**（既有）: 增加或透传 `structural_only`、`filter_reason` 等等效字段，或仅在 Document Tree 侧保留并在抽取时映射（见 Assumptions）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 以鼎信餐补标书为基准样例，管理员在确认向导中看到的默认 Bid Outline 节点数较当前生产基线减少 **≥30%**，且主要章节（报价表、参选响应函、技术方案等一级/二级标题）仍可直接找到。
- **SC-002**: 对含真实三级结构的标例文档，目录详情树形视图中 **≥80%** 的非 L1 节点显示在正确父节点下（人工抽检 20 个节点，至少 16 个父子关系正确）。
- **SC-003**: 解析完成后，管理员无需打开全部节点即可在 **10 秒内** 从任务/目录入口判断目录是否「过扁」（通过质量摘要中的 L1 占比与警告）。
- **SC-004**: 误报率可控：对登记的真章节标题集（≥20 条），增强后保留率 **≥95%**（不得因过滤规则大量删除真章节）。
- **SC-005**: 质量摘要与过滤统计的计算对 200MB 级 docm 文档增加的解析耗时 **<10%**（相对同文档增强前基线）。
- **SC-006**: 待确认任务列表中不再出现带 `error_message` 或未完成流水线的脏任务（100% 一致）。

## Assumptions

- **A-001**: 本特性**不引入 LLM** 做目录纠偏或 reorg；与 `2026-06-14-outline-hierarchy-inference-design.md` 决议一致；tender_doctor 的 LLM refine/reorg 留作后续独立特性。
- **A-002**: 被过滤出默认 Bid Outline 的段落**仍保留在 Document Tree** 中作为正文/其他节点，不删除源内容。
- **A-003**: 默认策略为「排除噪声节点不进 Bid Outline」（用户确认：向导方案 A）；被过滤节点在确认向导中**只读展示**于可展开列表，**不提供**一键恢复；误过滤通过 Document Tree 或重解析处理。
- **A-004**: 质量阈值初始建议：L1 占比 >60% 且节点数 >30 时警告；待复核占比 >40% 时警告；实现阶段可在 `plan.md` 中微调。
- **A-005**: 前端本阶段仅消费已有 API 字段做摘要展示（目录中心/确认向导轻量改动），不做完整树形编辑器重构。
- **A-006**: 本特性延续 Epic 3 范围，不修改模板库解析（Epic 2）行为，但规则模块设计应可复用。

## Out of Scope

- LLM 驱动的 chunk_layout refine / reorg（tender_doctor 完整逻辑树阶段）。
- PDF / PPT 格式的目录提取增强（当前 Epic 3 以 docx/docm 为主）。
- 版式启发式（字号、加粗、居中）推断标题。
- 候选知识生成规则变更（仅间接受益于更干净的章节映射）。
- 章节分类（Chapter Taxonomy）自动推荐准确率提升。

## Dependencies

- 已实现的层级推断模块：`docx_content_collector`、`docx_hierarchy_inferrer`、`docx_tree_materializer`、`heading_level_detector`。
- 已修复的 `persist_outline` `parent_id` 落库逻辑（2026-06-14 P0）。
- Epic 3 解析流水线统一推断快照修复（`walk_document` + `extract_toc_entries`，2026-06-14）。
- Epic 3 实际标书解析任务、确认向导、目录中心页面（只读展示扩展）。
- 代表性测试文档：鼎信餐补标书.docm 及现有 backend fixtures。

## Risks & Mitigations

| 风险 | 缓解 |
|------|------|
| 过滤规则过严，删除真章节 | 登记真章节基准集 + SC-004 保留率门禁；过滤原因可追溯 |
| 过滤规则过松，噪声仍多 | 分阶段上线：先日期/长句列举，再扩展；质量指标驱动迭代 |
| walk 与 extract 统一推断增加耦合 | 单一 `infer_result` 快照 + 单元/集成测试覆盖 |
| 大文档性能回退 | 过滤与质量统计在物化阶段 O(n) 完成，不增加额外全文扫描 |
