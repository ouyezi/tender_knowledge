# Feature Specification: Epic 6 生成辅助升级

**Feature Branch**: `008-generation-assist-upgrade`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "docs/epics/epic6-生成辅助升级.md"

**Source**: `docs/epics/epic6-生成辅助升级.md` · `docs/总需求.md` §6.16、§6.17、§11、§16.2、§17、§18 Phase 6、§19.4、§19.5、§20、§22

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 录入外部招标约束并获取模块组织建议 (Priority: P1)

标书编制人员在开始某一目标章节的草稿编制前，需要录入或确认外部招标约束（标书结构、
章节标题与层级、评分点、废标项、格式与资质要求、响应条款等），并基于产品分类、
项目类型、客户类型与目标章节获取模块组织建议，以便在人工确认后选定可参考的历史模块、
知识与素材组合。

**Why this priority**: 外部招标约束与模块组织建议是章节草稿生成的必要前置输入；
无此能力则无法启动符合 V3.0 原则的生成辅助流程。

**Independent Test**: 用户提交招标约束上下文与目标 outline 节点；系统返回模块组织建议，
每条包含推荐 KU、Wiki、素材、历史章节模块、组织顺序、评分点对应关系、废标风险提示
与来源追溯；用户可查看推荐理由并人工确认是否采用。

**Acceptance Scenarios**:

1. **Given** 用户已录入包含标书结构、评分点与废标项的外部招标约束，
   **When** 用户针对某目标章节请求模块组织建议，
   **Then** 系统返回推荐的历史模块、知识与素材，并附带与评分点的对应关系、
   废标风险提示、推荐理由与来源追溯。
2. **Given** 模块组织建议已生成，
   **When** 用户查看单条建议，
   **Then** 可看到 suggestion 标识、目标节点、推荐对象引用、风险标记与创建信息。
3. **Given** 用户已确认外部招标约束与推荐模块，
   **When** 用户标记某条建议为已采纳或已拒绝，
   **Then** 采纳状态被记录且可供后续章节草稿生成引用。
4. **Given** 用户发起模块组织建议请求，
   **When** 系统完成处理，
   **Then** 响应包含可用于下游生成链路的可追溯标识。

---

### User Story 2 - 配置模板章节变量并填写生成所需变量值 (Priority: P1)

标书编制人员需要为参与生成的 Template Chapter 查看、填写或确认变量值（如项目名称、
客户名称、产品名称、服务区域、交付周期等），以便生成内容中的占位符被正确替换，
且替换过程可被审计复现。

**Why this priority**: 变量配置与填写是章节草稿内容准确性的基础；MVP 阶段仅支持
简单占位符，须在本 Epic 内闭环。

**Independent Test**: 用户打开目标 Template Chapter 的变量列表；为必填变量填写值或
采用默认值；发起生成后，草稿中占位符被替换，且变量名与最终取值记录在生成快照中。

**Acceptance Scenarios**:

1. **Given** Template Chapter 已配置变量及默认值，
   **When** 用户查看该章节的变量列表，
   **Then** 可看到变量名称、是否必填及当前默认值。
2. **Given** 某变量标记为必填且用户未填写，
   **When** 用户尝试发起章节草稿生成，
   **Then** 系统阻止生成并提示需补全的变量。
3. **Given** 用户已为所有必填变量填写值或确认默认值，
   **When** 章节草稿生成完成，
   **Then** 草稿正文中对应占位符已被替换，且变量输入与取值被完整记录。
4. **Given** 变量仅支持简单占位符（不支持复杂表达式），
   **When** 用户配置或填写变量，
   **Then** 系统不提供表达式编辑能力，仅支持文本占位与替换。

---

### User Story 3 - 基于多源输入生成可追溯的章节草稿 (Priority: P1)

标书编制人员在确认外部招标约束、模块组织建议、知识包与变量值后，需要系统辅助生成
某一目标章节的草稿正文，且草稿每一段均可追溯到招标约束、模板章节、KU、Wiki、
素材或变量取值；生成时废标项与评分点 MUST 优先于模板库模块建议。

**Why this priority**: 章节草稿生成是 Epic 6 的核心交付物，直接体现 V3.0「检索优先、
约束优先、全链路可追溯」原则。

**Independent Test**: 用户选定目标 outline 节点并提交完整生成输入；系统返回章节草稿，
每段附带引用来源；当模板建议与招标要求冲突时展示冲突提示且不自动采用冲突内容；
输入优先级按：废标项 > 评分点 > 标书结构要求 > 用户人工选择 > 知识包 > 模板库模块建议。

**Acceptance Scenarios**:

1. **Given** 用户已确认招标约束、模块组织建议、知识包与变量值，
   **When** 用户发起目标章节的草稿生成，
   **Then** 系统返回章节草稿，且每段内容可追溯到至少一种来源
   （招标约束片段、Template Chapter、KU、Wiki、Manual Asset 或变量值）。
2. **Given** 招标约束中的废标项或评分点与模板库建议存在冲突，
   **When** 系统生成草稿，
   **Then** 系统 MUST 以招标约束为准，提示冲突风险，且 MUST NOT 静默采用
   与废标项或评分点冲突的模板内容。
3. **Given** 生成输入包含 Manual Asset 合规校验结果，
   **When** 某素材未通过合规校验或缺失，
   **Then** 草稿中标注缺失素材提示，且不伪造该素材内容。
4. **Given** 用户已人工选择某条件章节的启用状态，
   **When** 系统生成草稿，
   **Then** 用户人工选择优先于模板默认启用结果。
5. **Given** 章节草稿生成任务已提交，
   **When** 用户查询任务状态，
   **Then** 可获知处理中、已完成或失败状态及可读的错误说明（若失败）。

---

### User Story 4 - 查看生成快照以审计与复现生成结果 (Priority: P1)

标书编制人员或审核人员需要查看某次章节草稿生成所记录的 Generation Snapshot，
以便审计输入、引用来源、变量取值与生成版本，并在需要时理解或复现该次生成结果。

**Why this priority**: 全链路可追溯是 Constitution 非协商原则；无快照则无法支撑
合规审核与问题排查。

**Independent Test**: 用户完成一次章节草稿生成后，打开对应 Generation Snapshot；
可看到招标约束引用、模块建议引用、目标节点、使用的 KU/Wiki/Template Chapter/
Template Material、变量输入与值、检索 trace 摘要及生成结果版本标识。

**Acceptance Scenarios**:

1. **Given** 章节草稿生成已成功完成，
   **When** 用户查看该次 Generation Snapshot，
   **Then** 可看到 requirement_context 引用、suggestion 引用、target_outline_node、
   使用的知识对象与模板引用、变量输入与值、检索 trace 摘要及生成结果版本。
2. **Given** 同一目标章节存在多次生成记录，
   **When** 用户浏览历史快照列表，
   **Then** 可按时间或版本区分各次生成，且每次快照独立完整。
3. **Given** 审核人员需要验证某段草稿来源，
   **When** 从草稿段落跳转到快照详情，
   **Then** 可定位该段对应的来源对象与招标约束片段。

---

### User Story 5 - 处理条件章节建议与冲突风险提示 (Priority: P2)

标书编制人员需要系统根据产品分类、客户类型、招标关键词、必需资质或用户手工选择，
建议哪些 Template Chapter 条件章节可启用，并在与评分点或废标项冲突时收到明确风险
提示，而非被系统自动覆盖招标要求。

**Why this priority**: 条件章节提升模块建议的贴合度，但 MUST 服从外部招标约束；
属于增强编制体验的路径，依赖 P1 生成主流程就绪。

**Independent Test**: 用户满足某条件章节的启用条件；系统建议启用并展示理由；
当条件章节与招标评分点或废标项冲突时，系统标记风险且不作为默认采用项。

**Acceptance Scenarios**:

1. **Given** 目标章节关联的条件规则匹配当前产品分类或招标关键词，
   **When** 系统评估条件章节，
   **Then** 向用户展示建议启用的章节及匹配理由，最终是否启用由用户确认。
2. **Given** 条件章节与招标评分点或废标项存在冲突，
   **When** 系统展示条件章节建议，
   **Then** MUST 包含可见风险提示，且 MUST NOT 自动覆盖外部招标约束。
3. **Given** 用户对某条件章节做出手工启用或禁用选择，
   **When** 后续生成草稿，
   **Then** 用户选择优先于模板默认启用结果。

---

### User Story 6 - 重新生成、接受或废弃章节草稿 (Priority: P2)

标书编制人员对首次生成的章节草稿不满意或需迭代时，需要能够重新生成、正式接受某版
草稿进入后续编制流程，或废弃某次生成结果而不影响历史快照的可查性。

**Why this priority**: 生成辅助不替代人工决策；接受/废弃与重新生成是编制工作流的
自然延伸，依赖 P1 草稿与快照能力。

**Independent Test**: 用户对已完成草稿发起重新生成，产生新快照；用户将某版标记为
已接受或已废弃；已废弃结果仍可通过快照查询但不再作为默认活跃草稿。

**Acceptance Scenarios**:

1. **Given** 某目标章节已有生成完成的草稿，
   **When** 用户发起重新生成，
   **Then** 系统基于当前最新确认的输入产生新版草稿与新 Generation Snapshot，
   且不覆盖旧快照记录。
2. **Given** 用户对某版草稿满意，
   **When** 用户标记该结果为已接受，
   **Then** 该版本被记录为当前章节的接受稿，且状态可被查询。
3. **Given** 用户对某版草稿不满意，
   **When** 用户标记该结果为已废弃，
   **Then** 该版本不再作为默认活跃草稿，但其 Generation Snapshot 仍可审计查询。
4. **Given** 重新生成过程中发生失败，
   **When** 用户查看任务状态，
   **Then** 收到失败说明且可重试；已成功的前序快照不受影响。

---

### Edge Cases

- 外部招标约束缺少评分点或废标项时：系统按已有约束生成，并在快照中标注缺失项，
  不伪造评分点或废标项内容。
- 模块组织建议为空（知识库无匹配历史模块）时：系统仍可基于知识包与招标约束生成草稿，
  并提示无历史模块可参考。
- 所有推荐模板章节均与招标要求冲突时：草稿以招标约束为准，全部冲突项标记 risk_flags，
  不推荐自动采用任何冲突模板章节。
- 必填变量未填写时：阻止生成并列出待填变量，不产生不完整快照。
- 生成任务超时或中断时：用户收到可重试提示；若已产生 partial 记录，可供排查且不
  污染已接受版本。
- 用户废弃当前唯一草稿后：目标章节回到「无活跃草稿」状态，历史快照仍可查询。
- 未发布或已废弃的知识资产：MUST NOT 作为生成输入或引用来源出现在正式草稿中。
- 同一目标章节并发发起多次生成时：各任务独立追踪，以用户最终接受的那版为准。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 支持外部招标约束（Tender Requirement Context）作为服务层
  最高优先级输入，至少包含：标书结构要求、章节标题与层级、各章节评分点、废标项、
  格式要求、资质或证明材料要求、响应条款。
- **FR-002**: 系统 MUST 支持基于招标约束、产品分类、项目类型、客户类型、目标章节
  与过滤条件创建与查询 Module Assembly Suggestion。
- **FR-003**: Module Assembly Suggestion MUST 包含：推荐 KU、Wiki、素材、历史章节模块、
  推荐组织顺序、与评分点的对应关系、废标项风险提示、推荐理由、来源追溯及状态信息；
  MUST NOT 将建议等同于最终标书结构或模板实例。
- **FR-004**: 系统 MUST 支持 Template Chapter 变量配置：变量可设默认值、可标记必填；
  MVP 阶段仅支持简单文本占位符，不支持复杂表达式。
- **FR-005**: 系统 MUST 支持条件章节规则评估，启用条件至少包括：产品分类匹配、
  客户类型匹配、招标要求关键词、必需资质存在、用户手工选择；条件章节仅作建议，
  MUST NOT 覆盖外部招标约束。
- **FR-006**: 章节草稿生成输入 MUST 包含：Tender Requirement Context、
  Module Assembly Suggestion、Template Chapter 规则、Product Category、
  Bid Outline Node、KU/Wiki Knowledge Pack、Manual Asset 合规校验结果、变量值；
  MUST NOT 仅以知识包或模板库作为主输入。
- **FR-007**: 生成输入优先级 MUST 为：废标项 > 评分点 > 标书结构要求 > 用户人工选择
  > 知识包 > 模板库模块建议。
- **FR-008**: 章节草稿输出 MUST 包含：正文草稿、每段引用来源、使用的外部招标约束摘要、
  使用的模板库参考模块、使用的变量、冲突提示、缺失素材提示。
- **FR-009**: 当模板章节与招标评分点或废标项冲突时，系统 MUST 提示风险且 MUST NOT
  自动采用冲突模板内容。
- **FR-010**: 每次成功的章节草稿生成 MUST 产生 Generation Snapshot，至少记录：
  requirement_context 引用、suggestion 引用、target_outline_node、使用的 KU/Wiki/
  Template Chapter/Template Material、变量输入与值、检索 trace 摘要、生成 prompt 版本、
  生成结果版本。
- **FR-011**: 系统 MUST 支持创建章节草稿、查询生成任务状态、查询 Generation Snapshot、
  重新生成章节草稿、接受或废弃生成结果。
- **FR-012**: 模块组织建议能力 MUST 与 Epic 5 已提供的建议查询能力衔接；本 Epic 侧重
  建议的创建确认及向生成侧的完整消费，而非重复建设目录级检索基础能力。
- **FR-013**: 未确认 Candidate Knowledge MUST NOT 作为章节草稿生成的正式输入或引用来源。
- **FR-014**: 本 Epic MUST NOT 替代投标人员决策、自动决定最终标书结构、实现完整招标
  文件解析、评分规则管理、废标项判定、Word 多人协同编辑或标书最终排版与 PDF 交付。
- **FR-015**: Template Instance 完整配置与生成 MUST NOT 纳入本 Epic 主线范围，仅作为
  后续扩展预留。

### Key Entities *(include if feature involves data)*

- **Tender Requirement Context**: 外部招标约束输入，非知识库内部资产；含结构、评分点、
  废标项、格式、资质与响应条款等，为生成最高优先级上下文。
- **Module Assembly Suggestion**: 针对目标 outline 节点在特定招标约束下的模块组织建议；
  含推荐对象引用、组织顺序、评分点对应、风险标记、理由、来源追溯与采纳状态。
- **Template Chapter Variable**: 模板章节中的可替换占位符定义，含名称、默认值、
  是否必填；MVP 仅支持简单文本占位。
- **Conditional Chapter Rule**: 决定某 Template Chapter 是否建议启用的条件集合
  （产品分类、客户类型、招标关键词、资质、用户选择）；输出为建议而非强制结构。
- **Chapter Draft**: 某一目标 outline 节点的一次生成正文结果，含分段内容与逐段来源引用。
- **Generation Snapshot**: 单次生成的完整审计记录，关联输入、引用对象、变量、
  trace 摘要与版本信息，支持复现与审核。
- **Generation Task**: 章节草稿生成异步任务，含状态（处理中、完成、失败）与
  关联的快照或错误信息。
- **Draft Outcome Status**: 用户对某次生成结果的处理状态（待处理、已接受、已废弃）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 标书编制人员可在确认招标约束与模块建议后，于单次操作内发起目标章节
  草稿生成并在合理等待时间内（典型章节初稿，建议端到端不超过 3 分钟）获得带引用
  来源的草稿结果或明确的失败/进行中状态。
- **SC-002**: 在验收测试集中，100% 的已成功生成草稿的段落均可追溯到至少一种明确来源
  （招标约束、Template Chapter、KU、Wiki、Manual Asset 或变量值）。
- **SC-003**: 在包含招标约束与模板冲突的测试用例中，100% 的生成响应包含可见冲突
  或 risk 提示，且无静默采用冲突模板章节的情况。
- **SC-004**: 100% 的成功生成记录均产生完整 Generation Snapshot，且审核人员可在
  2 分钟内从草稿定位到对应快照中的输入、变量与引用明细。
- **SC-005**: 必填变量未填写的生成请求拦截率 100%；已填变量的替换结果与快照记录
  一致性在验收用例中达到 100%。
- **SC-006**: 用户接受/废弃/重新生成操作成功率 ≥99%，且操作后状态与快照历史可
  正确查询，不因状态变更丢失审计记录。
- **SC-007**: 在标注了废标项与评分点的测试场景中，生成内容对废标项与评分点的响应
  优先于模板库建议在人工评审抽样中达到业务设定的一致性目标（建议初始 ≥95%）。

## Assumptions

- Epic 0（Product Category、Chapter Taxonomy）、Epic 2（Template Chapter、Template Variable、
  Template Rule）、Epic 4（正式 KU、Wiki、Template Chapter、Manual Asset 已发布）、
  Epic 5（Module Assembly Suggestion 与 Knowledge Pack 基础能力）均已可用。
- 外部招标约束由用户或上游流程录入/确认；本 Epic 不建设完整招标文件解析系统。
- 模块组织建议的目录级检索与初版建议 API 由 Epic 5 提供；本 Epic 扩展建议创建确认
  及生成侧消费，不重复实现检索基础能力。
- Template Chapter 变量 MVP 仅支持简单占位符；复杂表达式与 Template Instance 完整
  实例化留待后续扩展。
- Manual Asset 合规校验结果由既有或并行能力提供；本 Epic 消费校验结果并在缺失时提示。
- 章节草稿生成为辅助能力，不自动决定最终标书结构；用户 MUST 人工确认模块建议与
  草稿采纳。
- V3.0 权限模型暂缓；生成与快照相关操作仍记录审计日志。
- 生成任务 MAY 异步执行；用户通过任务状态查询获知进度，典型失败场景须可重试。

## Dependencies

| 依赖 | 说明 |
|------|------|
| Epic 0 | 产品分类与章节分类底座 |
| Epic 2 | Template Chapter、Template Variable、Template Rule |
| Epic 4 | 正式 KU、Wiki、Template Chapter、Manual Asset 已发布 |
| Epic 5 | Module Assembly Suggestion 与 Knowledge Pack 基础能力、模块建议查询 API |

## Out of Scope

- 完整招标文件解析系统
- 评分规则管理系统
- 废标项判定系统
- Word 多人实时协同编辑
- 标书最终排版与 PDF 交付
- 自动替用户完成所有章节取舍或决定最终标书结构
- Template Instance 完整配置与生成（高级预留，后续扩展）
- 更复杂的条件章节表达式规则
- 多章节联动生成
- 与真实投标项目结果关联的模板效果分析
