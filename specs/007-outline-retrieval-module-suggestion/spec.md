# Feature Specification: Epic 5 目录级检索与模块建议

**Feature Branch**: `007-outline-retrieval-module-suggestion`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "docs/epics/epic5-目录级检索与模块建议.md"

**Source**: `docs/epics/epic5-目录级检索与模块建议.md` · `docs/总需求.md` §6.16、§10、§13、§15.4、§15.7、§16.2、§17、§18 Phase 4/5、§19.3、§19.4、§19.6、§20、§22

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 基于目标目录检索历史结构与章节模板 (Priority: P1)

标书编制人员在选定产品分类并输入外部招标约束中的目标目录、章节标题或评分点后，
需要系统检索相似历史投标目录、模板章节与常见章节模式，并获得可解释的匹配评分，
以便快速找到可参考的目录结构与模块组织方式。

**Why this priority**: 目录级检索是 Epic 5 的核心入口能力；无此能力，后续模块建议、
缺失诊断与知识推荐均无法启动。

**Independent Test**: 用户输入产品分类与目标章节标题列表；系统返回相似 Bid Outline、
Template Chapter、Chapter Pattern 及 match_score、coverage_rate、score_detail；
结果按产品分类过滤，不适用分类的素材不出现。

**Acceptance Scenarios**:

1. **Given** 产品分类与目标章节标题已选定，**When** 用户发起目录级检索，
   **Then** 系统返回相关历史投标目录节点、模板章节与章节模式，且每条结果包含
   匹配评分与命中原因说明。
2. **Given** 目标目录包含多个层级章节，**When** 系统完成章节标题标准化并匹配章节分类，
   **Then** 返回结果的 coverage_rate 反映已匹配目标章节数占目标章节总数的比例。
3. **Given** 检索请求指定了产品分类，**When** 系统返回知识或素材推荐，
   **Then** 不适用该产品分类的素材 MUST NOT 出现在结果中。
4. **Given** 用户仅选择产品分类与目标章节、未输入完整招标文本，
   **When** 用户发起知识检索，
   **Then** 系统优先推荐相关 Knowledge Unit、Template Chapter 与 Chapter Pattern。

---

### User Story 2 - 获取模块组织建议并覆盖招标约束 (Priority: P1)

标书编制人员在具备产品分类、项目类型、客户类型及外部招标文件结构要求、评分点、
废标项与目标章节要求时，需要系统生成模块组织建议：推荐模板章节或历史章节模块、
关联知识与素材、组织顺序与组合方式，并说明与招标要求的覆盖度、缺失章节与风险。

**Why this priority**: 模块组织建议是 Epic 5 面向业务的核心交付物；Epic 6 将消费
Module Assembly Suggestion 与升级后的 Knowledge Pack 生成章节草稿。

**Independent Test**: 用户提交招标约束上下文与 outline 节点；系统返回 module_suggestions，
每条包含推荐对象 ID、match_score、coverage_rate、评分点覆盖、废标风险、risk_flags
及可追溯推荐理由；当模板与招标要求冲突时展示风险提示而非静默采用模板。

**Acceptance Scenarios**:

1. **Given** 用户已输入外部招标约束、目标目录与产品分类，
   **When** 用户请求模块组织建议，
   **Then** 系统返回推荐的历史模块、知识与素材，并附带评分点覆盖情况、废标风险、
   缺失素材提示与推荐理由。
2. **Given** 招标文件结构要求、评分点或废标项与模板库建议存在冲突，
   **When** 系统生成模块建议，
   **Then** 系统 MUST 提示风险并 MUST NOT 自动采用与招标要求冲突的模板章节。
3. **Given** 模块建议已生成，
   **When** 用户查看单条建议，
   **Then** 可看到推荐组织顺序与组合方式、可用知识与素材数量、来源追溯及
   score_detail。
4. **Given** 用户发起模块建议请求，
   **When** 系统完成处理，
   **Then** 响应包含可用于下游链路的 trace_id。

---

### User Story 3 - 诊断目标目录缺失章节 (Priority: P1)

标书编制人员或知识库管理员需要系统根据产品分类下高频 Chapter Pattern，
诊断目标目录是否缺少常见章节，以便在编制前补齐结构缺口。

**Why this priority**: 缺失章节诊断直接降低废标与漏项风险，与目录匹配同属 P1 价值路径。

**Independent Test**: 用户输入目标目录与产品分类；系统列出缺失的高频章节模式及判定依据
（出现频次或比例阈值）；用户可结合模块建议中的缺失提示交叉验证。

**Acceptance Scenarios**:

1. **Given** 目标目录与产品分类已提供，
   **When** 系统执行缺失章节诊断，
   **Then** 对同一产品分类下出现频次达到阈值（默认 ≥3 次或占比 ≥30%）的
   Chapter Pattern，若目标目录未覆盖则标记为缺失章节。
2. **Given** 缺失章节已识别，
   **When** 用户查看模块组织建议或目录匹配结果，
   **Then** 缺失章节提示与 coverage_rate、score_detail 一致展示。

---

### User Story 4 - 多类型知识检索与可配置检索上下文 (Priority: P2)

标书编制人员需要按检索意图（知识查阅、素材推荐、模块建议、追溯查询）检索多种
已发布知识对象，并携带业务上下文（产品分类、章节分类、知识类型、招标约束片段）
与召回/排序/返回配置，以获得精准且可解释的结果。

**Why this priority**: 统一检索请求模型支撑 trace、反馈与评测闭环，是优化检索准确率的基础。

**Independent Test**: 用户以不同 intent 发起检索，携带 product_category_ids、
chapter_taxonomy_ids、tender_requirement_context 及 top_k 等选项；返回结果包含
score、score_detail、命中原因与来源追溯；未确认候选知识不出现在结果中。

**Acceptance Scenarios**:

1. **Given** 用户指定检索意图与业务过滤条件，
   **When** 发起检索，
   **Then** 系统按意图应用相应召回与排序策略，返回带评分与来源追溯的结果列表。
2. **Given** 用户启用返回 trace 与评分明细选项，
   **When** 检索完成，
   **Then** 每次检索记录 query、intent、过滤条件、召回与排序策略及返回结果摘要到
   retrieval_trace。
3. **Given** 检索对象包含 KU、Wiki、Template、Template Chapter、Bid Outline、
   Chapter Pattern、Manual Asset，
   **When** 用户按知识类型与用途过滤，
   **Then** 仅返回匹配过滤条件的已发布资产。
4. **Given** 调用方调整 top_k、过滤条件或上下文扩展深度，
   **When** 发起检索，
   **Then** 系统按请求参数执行并在 trace 中记录实际使用的配置。

---

### User Story 5 - 提交检索反馈以优化召回 (Priority: P2)

标书编制人员或管理员在查看检索与建议结果后，需要标记有用/无用、误召回、漏召回，
并可补充期望结果，以便运营团队改进检索策略。

**Why this priority**: 反馈闭环是 Epic 5 持续优化检索准确率的核心机制。

**Independent Test**: 用户对某次检索结果提交采纳、复制、加入草稿或误/漏召回标记；
反馈与对应 trace_id 关联；漏召回可附带期望结果供人工审核。

**Acceptance Scenarios**:

1. **Given** 用户已查看某次检索结果，
   **When** 用户标记「有用」或「无用」、误召回或漏召回，
   **Then** 反馈与对应检索 trace 关联并持久化。
2. **Given** 用户标记漏召回，
   **When** 用户补充期望应召回的对象或描述，
   **Then** 补充内容随反馈一并保存供后续人工审核。
3. **Given** 用户采纳或复制某条推荐结果，
   **When** 系统记录行为，
   **Then** 采纳类反馈可用于采纳率统计并与 trace 关联。
4. **Given** 用户人工调整产品分类、章节类型或知识类型过滤，
   **When** 调整后重新检索或提交反馈，
   **Then** 调整行为可被记录用于分析。

---

### User Story 6 - 评测集管理与检索策略版本对比 (Priority: P2)

知识库管理员需要在管理后台维护检索评测集，对比不同检索策略版本在同一评测集上的
Recall@K、Precision@K、MRR、NDCG、采纳率、误/漏召回率及有来源结果占比，
并在发布策略变更前验证指标变化。

**Why this priority**: 策略版本管理与评测对比确保检索优化可度量、可回滚，满足
Constitution「检索优先于生成」原则。

**Independent Test**: 管理员创建或导入评测用例集，绑定策略版本 A 与 B，执行对比；
展示各指标差异；线上反馈转评测用例须经人工确认后方进入正式评测集。

**Acceptance Scenarios**:

1. **Given** 管理员已维护检索评测集，
   **When** 选择两个检索策略版本在同一评测集上执行对比，
   **Then** 系统展示 Recall@K、Precision@K、MRR、NDCG、采纳率、误召回率、
   漏召回率及有来源结果占比的对比结果。
2. **Given** 检索策略、提示词、嵌入或重排配置发生变更，
   **When** 变更发布，
   **Then** 每项配置 MUST 带有版本号，且可在评测集上复现对比。
3. **Given** 线上用户反馈产生潜在评测用例，
   **When** 管理员尚未人工确认，
   **Then** 该用例 MUST NOT 自动进入正式评测集。
4. **Given** 管理员人工确认反馈用例，
   **When** 纳入正式评测集，
   **Then** 该用例可用于后续策略版本对比。

---

### User Story 7 - 目录中心与检索优化中心管理 (Priority: P3)

知识库管理员需要在目录中心维护投标目录、节点编辑、章节分类映射与章节模式确认，
并在检索优化中心查看检索日志与 retrieval_trace、管理反馈与评测集、配置召回排序
策略参数。

**Why this priority**: 管理后台支撑数据治理与检索运营，依赖前置检索与反馈能力就绪后
方可充分发挥价值。

**Independent Test**: 管理员在目录中心编辑 Bid Outline 节点并查看目录相似度；
在检索优化中心打开某 trace 查看参数、召回与排序结果，调整策略配置并触发评测对比。

**Acceptance Scenarios**:

1. **Given** 管理员进入目录中心，
   **When** 浏览 Bid Outline 列表并编辑节点或确认 Chapter Pattern，
   **Then** 变更持久化且可用于后续目录匹配。
2. **Given** 管理员进入检索优化中心，
   **When** 按 trace_id 或时间范围查询检索日志，
   **Then** 可查看查询参数、过滤条件、召回结果、排序结果及 retrieval_trace 详情。
3. **Given** 管理员需要优化检索，
   **When** 在后台调整召回权重、向量召回、重排或上下文扩展等策略配置，
   **Then** 配置保存为带版本号的策略，并可在评测集上对比效果。
4. **Given** 目录匹配已完成，
   **When** 管理员查看目录相似度，
   **Then** 可看到历史目录与目标目录的 match_score、coverage_rate 与 score_detail。

---

### Edge Cases

- 目标目录为空或仅含一级标题时：系统返回明确提示，coverage_rate 按 0 或不可用状态
  展示，不伪造匹配结果。
- 产品分类下无历史 Bid Outline 或 Chapter Pattern 时：返回空结果与说明，建议用户
  扩大分类或仅依赖模板库与知识检索。
- 招标约束与所有模板章节均冲突时：模块建议以招标约束为准，全部冲突项标记 risk_flags，
  不推荐自动采用任何冲突模板章节。
- 检索请求过滤条件过严导致零结果时：返回零结果说明与放宽过滤的建议，trace 仍完整记录。
- 同一章节标题映射到多个章节分类时：score_detail 展示歧义说明，默认采用最匹配项并
  标注备选分类。
- 未发布或已废弃资产：MUST NOT 出现在检索与模块建议结果中。
- 策略版本对比时评测集为空或样本不足：阻止对比并提示先维护评测用例。
- 模块建议处理超时场景：用户收到可重试提示，已生成的 partial trace 可供排查（若适用）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 支持对已发布 Bid Outline、Bid Outline Node、Template Chapter、
  Chapter Pattern 的目录级检索与结构匹配。
- **FR-002**: 系统 MUST 支持对已发布 KU、Wiki、Template、Manual Asset 的检索，
  并 MUST 按知识类型与产品分类过滤结果。
- **FR-003**: 系统 MUST 在目录匹配前对章节标题执行标准化，并映射到 Chapter Taxonomy。
- **FR-004**: 系统 MUST 计算并返回可解释的 match_score，默认权重为：产品分类匹配 30%、
  章节分类覆盖 30%、标题语义相似 20%、层级顺序相似 10%、可用知识覆盖 10%。
- **FR-005**: 系统 MUST 计算 coverage_rate = 已匹配目标章节数 / 目标章节总数，
  并在目录匹配与模块建议结果中展示。
- **FR-006**: 系统 MUST 根据产品分类下 Chapter Pattern 频次（默认 ≥3 次或占比 ≥30%）
  诊断目标目录缺失章节。
- **FR-007**: 系统 MUST 提供模块组织建议（Module Assembly Suggestion 初版），输入包含
  产品分类、项目类型、客户类型、外部招标结构要求、评分点、废标项与目标章节要求。
- **FR-008**: 模块组织建议输出 MUST 包含：推荐 Template Chapter 或历史章节模块、
  推荐 KU/Wiki/素材、组织顺序与组合方式、招标要求覆盖度、缺失章节提示、可用知识数量、
  风险提示、推荐理由与来源追溯。
- **FR-009**: 外部招标文件的结构要求、评分点与废标项 MUST 优先于模板库建议；模板库
  仅作历史写法与小模块组织参考。
- **FR-010**: 当模板章节与招标要求冲突时，系统 MUST 提示风险且 MUST NOT 自动采用冲突
  模板章节。
- **FR-011**: 检索请求 MUST 支持业务上下文（产品分类、章节分类、知识类型、文件用途、
  招标约束片段）、检索意图、召回配置、排序配置与返回配置，而非仅纯文本 query。
- **FR-012**: 检索意图 MUST 至少支持：knowledge_lookup、material_recommend、
  module_suggestion、trace_lookup；不同意图 MAY 使用不同召回与排序策略。
- **FR-013**: 每次检索 MUST 将实际使用的参数与策略记录到 retrieval_trace；返回结果
  MUST 包含 score、score_detail、命中原因与来源追溯（当调用方请求时）。
- **FR-014**: Knowledge Pack MUST 扩展字段：product_category、chapter_taxonomy、
  template_chapter_hints、bid_outline_context、chapter_patterns、candidate_source、
  import_id、score_detail、hit_reason，以供下游消费。
- **FR-015**: 系统 MUST 采集检索反馈：点击、采纳、复制、加入草稿、有用/无用、误召回、
  漏召回（可附期望结果）、人工调整分类过滤。
- **FR-016**: 检索策略及相关配置（策略参数、提示词、嵌入、重排）MUST 版本化管理，
  并支持在同一评测集上对比优化前后指标。
- **FR-017**: 评测指标 MUST 包含 Recall@K、Precision@K、MRR、NDCG、采纳率、误召回率、
  漏召回率、有来源结果占比。
- **FR-018**: 线上反馈转评测用例 MUST 经人工确认后方可进入正式评测集。
- **FR-019**: 目录中心 MUST 支持 Bid Outline 列表、节点编辑、Chapter Taxonomy 映射、
  Chapter Pattern 确认、目录相似度查看。
- **FR-020**: 检索优化中心 MUST 支持：检索日志与 retrieval_trace 查看、反馈采集、
  评测集管理、策略版本指标对比、召回与排序策略配置管理。
- **FR-021**: 系统 MUST 提供模块组织建议、检索反馈与检索评测相关对外接口，响应结构
  包含 module_suggestions（含 suggestion_id、目标节点、推荐对象 ID、match_score、
  coverage_rate、评分点覆盖、废标风险、risk_flags）与 trace_id。
- **FR-022**: 未确认 Candidate Knowledge MUST NOT 作为检索或模块建议的正式输入或结果。
- **FR-023**: 本 Epic MUST NOT 实现章节草稿生成、Template Instance 完整实例化、
  复杂自动学习系统或招标文件完整解析系统。

### Key Entities *(include if feature involves data)*

- **Retrieval Request**: 一次检索或建议请求的业务上下文，含 query、intent、过滤条件、
  招标约束片段、召回/排序/返回选项。
- **Retrieval Trace**: 单次检索的全链路记录，关联 trace_id，含请求参数、策略版本、
  召回与排序中间结果摘要及最终返回。
- **Directory Match Result**: 目录级匹配输出，含相似 Bid Outline/节点、Template Chapter、
  Chapter Pattern、match_score、coverage_rate、score_detail。
- **Module Assembly Suggestion**: 针对目标 outline 节点的模块组织建议，含推荐对象引用、
  覆盖度、风险标记与推荐理由。
- **Chapter Gap Diagnosis**: 基于 Chapter Pattern 频次对目标目录的缺失章节判定结果。
- **Knowledge Pack (Extended)**: 面向下游的打包知识对象，扩展产品分类、章节分类、
  模板章节提示、目录上下文、章节模式、来源与评分明细等字段。
- **Retrieval Feedback**: 用户或管理员对某次检索结果的交互与评价，关联 trace_id。
- **Retrieval Eval Case / Eval Set**: 用于度量检索质量的用例与集合，可人工维护或由
  确认后的反馈转化。
- **Retrieval Strategy Version**: 可版本化的检索策略配置集合，含召回、排序、重排、
  上下文扩展等参数及关联的提示词与嵌入配置版本。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在输入产品分类与目标章节后，可在一次交互内获得带 match_score、
  coverage_rate 与 score_detail 的目录匹配结果；典型请求端到端感知等待时间不超过 2 秒
  （模块组织建议路径，不含大语言模型生成）。
- **SC-002**: 在维护的检索评测集上，策略优化迭代后 Recall@K 或 NDCG 相对基线版本
  可度量对比，且同一评测集可复现至少两个策略版本的指标差异报告。
- **SC-003**: 检索与模块建议结果中，有来源追溯信息的结果占比在评测集上达到业务设定的
  基线目标（建议初始基线 ≥90%），且每条主结果包含可读的命中原因或推荐理由。
- **SC-004**: 用户反馈（有用、无用、误召回、漏召回）提交成功率 ≥99%，且 100% 与
  对应 retrieval_trace 可关联查询。
- **SC-005**: 当招标约束与模板冲突时，100% 的模块建议响应在存在冲突场景下包含可见
  risk_flags 或 rejection_risks，且无静默采用冲突模板章节的情况（以评测用例与验收测试验证）。
- **SC-006**: 产品分类过滤生效：在分类标注明确的评测用例中，不适用产品分类的素材
  误召回率低于业务设定阈值（建议初始 <5%）。
- **SC-007**: 采纳率、误召回率、漏召回率可按周或按策略版本聚合展示，管理员可在
  检索优化中心完成策略版本对比而无需手工导出日志。

## Assumptions

- Epic 0（Product Category、Chapter Taxonomy）、Epic 2（Template Chapter、Template Material）、
  Epic 3（Bid Outline、Chapter Pattern）、Epic 4（候选知识已确认发布）均已可用；
  本 Epic 仅消费已发布知识资产。
- 章节标题标准化与 Chapter Taxonomy 映射复用分类底座与既有解析产物，本 Epic 不建设
  完整招标文件解析系统。
- match_score 初版采用可解释规则评分；复杂机器学习排序不在本 Epic 范围，但策略版本
  机制需预留扩展空间。
- 缺失章节默认阈值（频次 ≥3 或占比 ≥30%）为可配置参数，默认值按 Epic 文档执行。
- 检索评测集初始由管理员手工构建；线上反馈转用例须经人工确认，不假设全自动学习。
- V3.0 权限模型暂缓；管理后台操作仍记录审计日志，敏感检索日志访问受现有平台约束。
- Epic 6 将消费 Module Assembly Suggestion 与扩展 Knowledge Pack；本 Epic 不实现章节草稿生成。
- 目录级检索与模块建议的 P95 延迟目标对齐 Constitution：不含 LLM 的模块建议路径
  P95 < 2 秒（在典型数据规模与标准部署下验证）。

## Dependencies

| 依赖 | 说明 |
|------|------|
| Epic 0 | 产品分类与章节分类底座 |
| Epic 2 | 已发布 Template Chapter、Template Material |
| Epic 3 | Bid Outline、Bid Outline Node、Chapter Pattern |
| Epic 4 | 候选知识已确认并发布为正式资产 |
| Epic 6（下游） | 消费 Module Assembly Suggestion 与 Knowledge Pack |

## Out of Scope

- 章节草稿生成（Epic 6）
- Template Instance 完整实例化
- 复杂自动学习系统
- 招标文件完整解析系统
- 文件夹批量导入或未确认候选知识的正式检索暴露
