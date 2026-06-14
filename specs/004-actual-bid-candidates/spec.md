# Feature Specification: Epic 3 实际标书导入与候选知识

**Feature Branch**: `004-actual-bid-candidates`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "docs/epics/epic3-实际标书导入与候选知识.md"

**Source**: `docs/epics/epic3-实际标书导入与候选知识.md` · `docs/总需求.md` §6.1–6.3、§6.10–6.15、§8.1–8.3、§15.4、§17、§18 Phase 3 前半、§19.2、§20、§22

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 实际标书解析为文档结构 (Priority: P1)

知识库管理员在 Epic 1 中已将文件用途确认为 `actual_bid` 后，需要触发实际标书解析，
系统将文档转化为 Document 与 Document Tree，为目录抽取与候选知识生成提供结构化起点。

**Why this priority**: 文档结构解析是 Epic 3 的价值起点；无 Document 与 Document Tree，
后续 Bid Outline 抽取与 Candidate Knowledge 生成均无法开展。

**Independent Test**: 管理员选择一条已确认 `file_purpose = actual_bid` 的 File Import
并启动解析；解析完成后可查看 Document、章节树及关联的来源元数据，且原 File Import
记录保持完整。

**Acceptance Scenarios**:

1. **Given** File Import 已确认 `file_purpose = actual_bid`，**When** 管理员启动实际标书解析，
   **Then** 系统创建解析任务并生成 Document，且 Document 标记 `source_type = actual_bid`。
2. **Given** 实际标书解析任务执行中，**When** 管理员查询任务状态，
   **Then** 可查看进行中、成功或失败状态及可追溯的任务标识。
3. **Given** 实际标书含标题层级内容，**When** 解析完成，
   **Then** 系统生成 Document Tree，章节节点保留与源文档内容的对应关系。
4. **Given** 实际标书解析失败，**When** 管理员查看原 File Import，
   **Then** 源导入记录未被破坏，且可重新发起解析。
5. **Given** 管理员为实际标书关联产品分类或填写项目名称、客户名称，
   **When** 保存 Document 来源信息，
   **Then** 元数据持久化并可从 Document 详情查看。

---

### User Story 2 - 从实际标书抽取可编辑目录 (Priority: P1)

知识库管理员需要从已解析的实际标书中自动抽取 Bid Outline，并在目录中心查看、编辑、
合并或删除目录节点，形成可治理的标书目录结构。

**Why this priority**: Bid Outline 是实际标书资产化的核心结构对象；目录可编辑性直接
决定后续章节映射、候选生成与目录级检索（Epic 5）的质量。

**Independent Test**: 管理员对一份已解析的实际标书触发目录抽取；抽取完成后在目录中心
打开 Bid Outline，修改节点标题、层级或排序并保存；刷新后结构按人工编辑结果展示。

**Acceptance Scenarios**:

1. **Given** Document 与 Document Tree 已生成，**When** 管理员触发 Bid Outline 抽取，
   **Then** 系统优先使用文档内置目录生成 Bid Outline；无内置目录时使用标题样式与编号规则。
2. **Given** Bid Outline 已生成，**When** 管理员在目录中心编辑节点标题、层级、排序，
   **Then** 变更保存成功且 Bid Outline Node 状态反映人工编辑结果。
3. **Given** 管理员合并或删除 Bid Outline 节点，**When** 保存，
   **Then** 目录结构按操作结果更新，且操作写入审计日志。
4. **Given** 管理员编辑 Bid Outline，**When** 保存变更，
   **Then** Document Tree MUST NOT 被自动同步修改。
5. **Given** 文档被重新解析且与既有 Bid Outline 存在结构差异，**When** 系统完成解析，
   **Then** 仅生成 Bid Outline 差异建议，由管理员选择是否同步，不得静默覆盖已编辑目录。

---

### User Story 3 - 目录节点章节分类与产品分类映射 (Priority: P2)

知识库管理员需要将 Bid Outline Node 与 Document Tree Node 映射到 Chapter Taxonomy，
并确认或修正节点的产品分类，使目录结构具备可检索、可治理的语义标签。

**Why this priority**: 章节分类与产品分类是候选知识生成规则与后续检索过滤的基础；
需在目录可编辑后尽快支持映射与确认。

**Independent Test**: 管理员在目录中心为若干 Bid Outline Node 选择章节类型并关联
产品分类后保存；再次打开节点详情可看到已确认的映射结果。

**Acceptance Scenarios**:

1. **Given** Bid Outline 已生成，**When** 管理员为节点选择 Chapter Taxonomy，
   **Then** 映射结果持久化至 Bid Outline Node，且系统 MAY 展示机器建议供覆盖。
2. **Given** Document Tree Node 为实际标书章节，**When** 管理员确认章节类型与产品分类，
   **Then** 节点保留 `chapter_taxonomy_id` 与 `product_category_ids` 等目录沉淀字段。
3. **Given** 系统基于章节标题或内容给出分类建议，**When** 管理员人工修正，
   **Then** 人工结果优先于机器建议并写入审计记录。
4. **Given** 高价值章节节点已映射章节类型，**When** 触发候选生成，
   **Then** 该节点可作为 Candidate Knowledge 的来源节点被引用。

---

### User Story 4 - 从实际标书章节生成候选知识 (Priority: P2)

知识库管理员需要在实际标书解析与目录抽取完成后，由系统按章节类型从 Document Tree
章节中生成 Candidate Knowledge（含 KU、Wiki 候选），并在候选知识中心查看解析产出的
待确认列表，为 Epic 4 人工确认入库做准备。

**Why this priority**: 候选知识是 Epic 3 面向 Epic 4 的核心交付物；无候选生成则
实际标书无法进入知识资产治理链路。

**Independent Test**: 管理员对含技术方案、产品功能、资质类章节的实际标书完成解析与
目录映射后触发候选生成；在候选知识中心可查看 `pending` 状态候选列表，且每条候选
可追溯到 File Import、Document 与来源节点。

**Acceptance Scenarios**:

1. **Given** 章节类型为技术方案，**When** 候选知识生成完成，
   **Then** 系统生成方案类 KU 候选，状态为 `pending`。
2. **Given** 章节类型为产品功能，**When** 候选知识生成完成，
   **Then** 系统生成产品或能力说明类 KU 候选。
3. **Given** 章节类型为企业实力、资质或荣誉，**When** 候选知识生成完成，
   **Then** 系统生成资质或能力类 KU 候选。
4. **Given** 文档含稳定通用段落，**When** 候选知识生成完成，
   **Then** 系统 MAY 推荐为 Wiki 候选。
5. **Given** 候选知识已生成，**When** 用户通过正式检索或对外服务查询，
   **Then** 未确认候选 MUST NOT 作为正式检索结果返回。
6. **Given** 管理员查看某条 Candidate Knowledge，**When** 打开来源详情，
   **Then** 可追溯到 File Import、Document 与 Document Tree Node（或等效来源节点）。

---

### User Story 5 - 章节模式候选挖掘 (Priority: P3)

知识库管理员需要从多个实际标书 Bid Outline 与既有 Template Chapter 中归纳章节模式，
生成待确认的 Chapter Pattern 候选，为后续正式治理（Epic 4）提供模式资产起点。

**Why this priority**: Chapter Pattern 提升目录级组织与推荐能力，但依赖足够 Bid Outline
与模板章节数据；可在主解析与候选生成链路就绪后交付。

**Independent Test**: 管理员在具备多个 Bid Outline 的环境下触发章节模式挖掘任务；
任务完成后可查看 `pending` 状态的 Chapter Pattern 候选及其来源概要。

**Acceptance Scenarios**:

1. **Given** 系统存在多个 Bid Outline 或 Template Chapter 样本，**When** 管理员触发
   `chapter_pattern_mining` 任务，
   **Then** 系统生成 Chapter Pattern 候选，确认与正式治理留待 Epic 4。
2. **Given** 章节模式挖掘任务执行中或已完成，**When** 管理员在任务中心查看，
   **Then** 可看到任务状态、关联对象与错误信息（若失败）。

---

### User Story 6 - 目录中心与任务可观测性 (Priority: P3)

知识库管理员需要在管理后台的目录中心管理 Bid Outline、查看目录抽取与候选生成任务日志，
并在候选知识中心浏览解析产生的候选列表（只读，不含确认发布能力）。

**Why this priority**: 运营可观测性与日常管理界面支撑治理效率；确认发布由 Epic 4 提供，
本 Epic 仅需列表可见与任务追溯。

**Independent Test**: 管理员在目录中心打开 Bid Outline 列表、进入节点编辑并查看抽取
任务日志；在候选知识中心可筛选查看 `pending` 候选，但无确认或发布按钮。

**Acceptance Scenarios**:

1. **Given** 系统存在若干 Bid Outline，**When** 管理员打开目录中心，
   **Then** 可浏览列表并按实际标书或项目维度定位目录。
2. **Given** 目录抽取或候选生成任务已执行，**When** 管理员查看任务日志，
   **Then** 可看到 `bid_outline_extract`、`candidate_knowledge_generate`、
   `chapter_pattern_mining` 等任务类型的状态与 trace 关联信息。
3. **Given** 解析已产生 Candidate Knowledge，**When** 管理员打开候选知识中心，
   **Then** 可查看候选列表与来源摘要，但 MUST NOT 在本 Epic 提供确认、合并、
   拆分或发布操作。

---

### Edge Cases

- 实际标书无内置目录且标题样式混乱时，系统 MUST 生成初始扁平或最小层级 Bid Outline
  并标记待人工整理，而非抽取失败。
- 同一 File Import 重复触发解析时，系统 MUST 提示已有任务或结果，并允许重新处理
  而不破坏原 File Import。
- 解析过程中源文件不可读时，任务 MUST 标记失败并保留错误原因，File Import 记录
  保持可查。
- 管理员编辑 Document Tree 后，已人工确认或编辑过的 Bid Outline MUST NOT 被自动覆盖；
  仅可通过差异建议由人工决定是否同步。
- 文档重新解析后，系统 MUST 对 Bid Outline 仅生成差异建议，不得静默覆盖人工编辑结果。
- 章节无法映射到任何 Chapter Taxonomy 时，节点 MUST 保留未映射状态并允许管理员
  后续补全，而非阻断整份文档的候选生成。
- 某章节内容过短或无可提取知识时，系统 MAY 跳过该章节的候选生成并记录原因，而非
  任务整体失败。
- 超大实际标书（如数百页）时，解析与候选生成 MUST 按章节或块分批处理，不得因单次
  处理体量过大而导致任务不可恢复失败。
- 招标文件评分点、废标项解析不在本 Epic 范围；相关入口 MUST NOT 在本阶段提供。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 仅对 File Import 已确认 `file_purpose = actual_bid` 的记录
  启动实际标书解析与后续 Bid Outline、Candidate Knowledge 生成任务。
- **FR-002**: 系统 MUST 在实际标书导入解析时创建或更新 Document，并扩展来源字段：
  `import_id`、`source_type`、`source_usage`、`product_category_ids`、
  `bid_project_name`、`bid_customer_name`；其中 `source_type` MUST 为 `actual_bid`。
- **FR-003**: 系统 MUST 将实际标书解析为 Document Tree，且章节节点扩展目录沉淀字段：
  `chapter_taxonomy_id`、`product_category_ids`、`is_outline_node`、
  `candidate_template_chapter_id`、`candidate_pattern_id`（按场景填充）。
- **FR-004**: 系统 MUST 在实际标书解析完成后支持同时产出 Document Tree、Bid Outline
  与 Candidate Knowledge 候选（候选生成 MAY 为独立异步任务）。
- **FR-005**: 系统 MUST 在实际标书导入后自动生成 Bid Outline 及 Bid Outline Node；
  节点含 `outline_node_id`、`bid_outline_id`、`parent_id`、`title`、`level`、
  `sort_order`、`chapter_taxonomy_id`、`source_node_id`、`product_category_ids`、
  `status` 等关键属性。
- **FR-006**: Bid Outline 抽取 MUST 优先使用文档内置目录；其次使用标题样式与编号规则。
- **FR-007**: 系统 MUST 支持用户在目录中心编辑 Bid Outline：修改、合并、删除节点；
  用户编辑 Bid Outline MUST NOT 自动修改 Document Tree。
- **FR-008**: 用户编辑 Document Tree MUST NOT 自动覆盖已确认或已人工编辑的 Bid Outline。
- **FR-009**: 文档重新解析后，系统 MUST 仅生成 Bid Outline 差异建议，由人工选择是否同步。
- **FR-010**: 系统 MUST 支持将 Bid Outline Node 与 Document Tree Node 映射到
  Chapter Taxonomy，并支持产品分类的确认与修正；人工结果优先于机器建议。
- **FR-011**: 系统 MUST 建立 Document Tree 与 Bid Outline 的关联（通过 `source_node_id`
  等来源链），且关联在重解析时保持可追溯。
- **FR-012**: 系统 MUST 按章节类型规则生成 Candidate Knowledge 候选：
  技术方案 → 方案类 KU；产品功能 → 产品或能力说明类 KU；供应链 → 能力说明或方案类 KU；
  企业实力/资质/荣誉 → 资质或能力类 KU；稳定通用段落 → MAY 推荐 Wiki 候选。
- **FR-013**: 本 Epic 生成的 Candidate Knowledge MUST 默认为 `pending` 状态；确认、
  合并、拆分、批量确认与发布 MUST NOT 在本 Epic 实现（归属 Epic 4）。
- **FR-014**: 每条 Candidate Knowledge MUST 保留完整来源链：File Import、Document、
  Document Tree Node（或等效来源节点）。
- **FR-015**: 未确认的 Candidate Knowledge MUST NOT 参与正式检索或作为对外知识服务输入。
- **FR-016**: 系统 MUST 支持从多个 Bid Outline 与 Template Chapter 挖掘 Chapter Pattern
  候选；本 Epic 仅生成候选，确认与正式治理归属 Epic 4。
- **FR-017**: 系统 MUST 提供任务类型：`bid_outline_extract`、`candidate_knowledge_generate`、
  `chapter_pattern_mining`；任务失败 MUST NOT 破坏或删除原 File Import 与 Document 记录。
- **FR-018**: 系统 MUST 在目录中心提供：Bid Outline 列表、Bid Outline 节点编辑、
  Chapter Taxonomy 映射、目录抽取任务日志查看。
- **FR-019**: 系统 MUST 在候选知识中心提供由解析产生的候选列表查看能力；MUST NOT
  在本 Epic 提供候选确认、合并、拆分或发布界面。
- **FR-020**: 实际标书解析、目录编辑、分类映射、候选生成与任务执行 MUST 写入可追溯
  的审计日志，且关键步骤 MUST 可关联 trace 标识。
- **FR-021**: 系统 MUST NOT 在本 Epic 实现：Candidate Knowledge 确认与发布、候选知识
  合并/拆分/批量确认、目录级检索、模板推荐、招标文件评分点或废标项解析。
- **FR-022**: 凡需智能辅助的步骤（章节分类建议、候选内容提取、模式归纳）MUST 将输出
  放入候选区或待确认差异，不得静默写入正式知识资产。
- **FR-023**: 对超大文档，解析与候选生成 MUST 以章节或内容块为处理单元分批执行，
  MUST NOT 要求单次处理整份文件内容而导致不可恢复失败。

### Key Entities *(include if feature involves data)*

- **Document**: 实际标书的结构化文档对象；含来源元数据（导入关联、来源类型、
  用途、产品分类、项目名称、客户名称）；解析后可关联 Document Tree、Bid Outline
  与 Candidate Knowledge。
- **Document Tree Node**: 文档章节树节点；含章节分类、产品分类、是否目录节点、
  候选模板章节与候选模式引用等目录沉淀字段；可作为候选知识来源节点。
- **Bid Outline**: 实际标书或目标标书的目录结构；导入后自动生成，支持人工编辑；
  确认后可参与后续目录检索与模块组织建议（Epic 5）。
- **Bid Outline Node**: 目录中的单个节点；含层级、排序、章节分类、来源节点、
  产品分类与状态；与 Document Tree Node 通过来源链关联。
- **Chapter Pattern**: 从多个 Bid Outline 与 Template Chapter 归纳的章节模式；
  本 Epic 仅产生待确认候选。
- **Candidate Knowledge**: 从文档章节提取但尚未确认的知识候选；含 `pending` 状态、
  知识类型意向与完整来源链；经 Epic 4 确认后成为正式 KU、Wiki 等资产。
- **Actual Bid Parse Task**: 实际标书解析、目录抽取、候选生成或模式挖掘的异步任务；
  关联 File Import 与 Document，含状态与错误信息。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理员可在单次操作链路内（用途已确认为 actual_bid → 解析 → 目录抽取）
  将一份实际标书转化为含 Document Tree 与可编辑 Bid Outline 的结构化资产，熟练用户
  全流程可在 45 分钟内完成（不含大规模手工目录整理）。
- **SC-002**: 对含标准内置目录或数字编号标题结构的实际标书，自动抽取的 Bid Outline
  与文档目录层级一致率达到 85% 以上（以人工编辑前自动结果计）。
- **SC-003**: 100% 的实际标书解析或候选生成失败场景保留完整 File Import 与 Document
  记录，且管理员可在同一导入记录上重新发起任务而无需重新上传文件。
- **SC-004**: 管理员在目录中心完成 Bid Outline 节点编辑、章节分类与产品分类映射后，
  保存结果 100% 在再次打开时一致呈现。
- **SC-005**: 100% 的 Candidate Knowledge 候选均可从候选详情追溯到 File Import、
  Document 与来源节点。
- **SC-006**: 未确认候选知识在正式检索场景中的返回率为 0%。
- **SC-007**: 文档重新解析后，100% 的 Bid Outline 结构冲突以差异建议形式呈现，
  无静默覆盖人工编辑目录的案例。
- **SC-008**: 所有解析、目录编辑、分类映射与候选生成关键操作均可通过审计日志关联至
  具体操作者与时间戳，满足 100% 关键操作可追溯。
- **SC-009**: 90% 的管理员可在首次使用时，在无额外培训情况下完成「解析 → 目录抽取
  → 查看候选列表」主流程（以内部可用性走查计）。

## Assumptions

- Epic 0（Product Category、Chapter Taxonomy）已可用；管理员可选择产品分类与章节分类。
- Epic 1（File Import、`file_purpose = actual_bid` 确认）已可用；本 Epic 不重复实现
  文件上传与用途确认能力。
- 目标用户为知识库管理员或具备同等权限的内容治理人员；V3.0-MVP 暂不区分细粒度角色权限。
- 实际标书源文件主要为 docx；其他扩展名依文件类型选择解析策略，MVP 以 docx 为主路径。
- Candidate Knowledge 的确认、合并、拆分、发布与治理由 Epic 4 负责；本 Epic 仅创建
  `pending` 候选并支持列表查看。
- 目录级检索与模板推荐由 Epic 5 消费已治理的 Bid Outline 与 Chapter Pattern；本 Epic
  不实现检索与推荐能力。
- 智能辅助（分类建议、内容提取、模式挖掘）遵循 Constitution：输出进入候选区或待确认
  差异；人工确认门在 Epic 4 执行，但本 Epic 产生的候选默认不可用于正式检索。
- 「确认后的 Bid Outline」参与目录检索的具体机制由 Epic 5 实现；本 Epic 保证目录可编辑、
  可映射且状态可区分。
- 单文件导入为 MVP 范围；文件夹批量导入不在本 Epic 范围。
- 大文件处理假设：先结构解析得到 Document Tree 与目录候选，再按章节调度候选生成与
  智能辅助，不存在整文件单次处理的依赖路径。
- Document Tree 在本 Epic 为只读追溯；章节与产品分类映射仅在 Bid Outline 上编辑。
- FR-022 章节分类 LLM 建议本阶段为规则-only；LLM 增强推迟 Epic 4 或后续特性。
- 解析任务日志通过目录中心待办表 Drawer 展示，不实现独立 ParseTaskLogPanel 页面。
- 「新建目录」不在 MVP 范围；目录由解析自动生成。

## Dependencies

- **Epic 0**（前置）: Product Category、Chapter Taxonomy 分类底座。
- **Epic 1**（前置）: File Import、文件用途确认为 `actual_bid`、导入审计与存储。
- **Epic 2**（弱依赖）: Template Chapter 作为 Chapter Pattern 挖掘的样本来源之一。
- **Epic 4**（下游）: 接收 Candidate Knowledge 与 Chapter Pattern 候选，负责确认与发布。
- **Epic 5**（下游）: 使用 Bid Outline、Bid Outline Node、Chapter Pattern 做目录级检索。
