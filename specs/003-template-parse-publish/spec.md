# Feature Specification: Epic 2 模板库解析与发布

**Feature Branch**: `003-template-parse-publish`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "docs/epics/epic2-模板库解析与发布.md"

**Source**: `docs/epics/epic2-模板库解析与发布.md` · `docs/总需求.md` §6.4–6.9、§7、§15.2、§17、§18 Phase 2、§19.1、§20、§22

## Clarifications

### Session 2026-06-12

- Q: 分类粒度应落在文件还是提取后的知识块？ → A: 对提取出的知识库块（Candidate Knowledge / 章节片段 / Template Material 等）进行分类；导入文件本身可能是完整标书、标书模板、产品方案或资质合集，不对文件做细粒度小分类。
- Q: 大模型调用如何配置与切换？ → A: 通过环境变量（`LLM_PROVIDER`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`）配置；默认使用千问（Qwen）兼容 OpenAI 接口；未配置 Key 或调用失败时降级为规则引擎，不阻塞主流程。
- Q: 大文件是否可整文件一次性 LLM 处理？ → A: 否；导入文件可能很大，LLM 仅对按章节/段落/素材切分后的知识块分批调用，整文件 MUST NOT 一次性送入模型。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 模板文件解析为结构化资产 (Priority: P1)

知识库管理员在 Epic 1 中已将文件用途确认为 `template_file` 后，需要触发模板解析，
系统将文档标题结构、固定段落、表格与图片转化为 Template、Template Chapter 树与
Template Material，并生成待人工确认的知识候选，形成可治理的模板资产起点。

**Why this priority**: 模板解析是 Epic 2 的核心价值交付；无结构化 Template 与章节树，
后续编辑、发布与模板推荐均无法开展。

**Independent Test**: 管理员选择一条已确认 `template_file` 的 File Import 并启动解析；
解析完成后可查看生成的 Template、章节树与素材列表，且原 File Import 记录保持完整。

**Acceptance Scenarios**:

1. **Given** File Import 已确认 `file_purpose = template_file`，**When** 管理员启动模板解析，
   **Then** 系统创建解析任务并基于文档标题结构生成 Template Chapter 树，且章节顺序
   遵循文档内前缀数字排序规则。
2. **Given** 模板文档含固定段落、表格或图片，**When** 解析完成，
   **Then** 系统生成 Template Material 或 Candidate Knowledge 候选，并保留与源章节的关联。
3. **Given** 文件名含产品名或章节名，**When** 解析完成，
   **Then** 系统展示产品分类与章节类型的建议，供后续人工确认界面使用。
4. **Given** 模板解析任务执行中，**When** 管理员查询任务状态，
   **Then** 可查看进行中、成功或失败状态及可追溯的任务标识。
5. **Given** 模板解析失败，**When** 管理员查看原 File Import，
   **Then** 源导入记录未被破坏，且可重新发起解析。

---

### User Story 2 - 解析结果人工确认 (Priority: P2)

知识库管理员在模板解析完成后，需要在人工确认界面逐项审核并修正系统建议，包括模板库
归类、产品分类、章节层级与类型、是否作为固定模板章节、是否提取为 KU 或 Wiki、
以及是否忽略特定节点或素材。

**Why this priority**: 人工确认门是 V3.0 核心治理原则；未经确认的解析结果 MUST NOT
作为正式模板资产或后续检索/推荐输入。

**Independent Test**: 管理员打开某次模板解析的确认界面，修改章节层级、章节类型与
产品分类后保存；保存后变更持久化，且人工修正结果优先于机器解析结果。

**Acceptance Scenarios**:

1. **Given** 模板解析已完成，**When** 管理员进入人工确认界面，
   **Then** 可逐项确认 Template Library 归类、产品分类、Template Chapter 层级、
   章节类型、固定章节标记、KU/Wiki 提取意向及忽略标记。
2. **Given** 管理员修改章节层级或排序，**When** 保存确认结果，
   **Then** 变更持久化，且后续自动重解析 MUST NOT 直接覆盖已确认结构，仅可产生
   待确认差异。
3. **Given** 管理员将某节点标记为忽略，**When** 保存，
   **Then** 该节点不参与正式 Template Chapter 树，且保留审计记录。
4. **Given** 管理员确认将某素材提取为 KU 或 Wiki 候选，**When** 保存，
   **Then** 生成 Candidate Knowledge 供 Epic 4 后续治理，且未确认前 MUST NOT
   作为正式知识资产对外可用。

---

### User Story 3 - 模板章节树与素材编辑 (Priority: P2)

知识库管理员需要在前台管理界面查看并编辑 Template Chapter 树，调整章节标题、层级、
排序、章节类型、产品分类、必填标记与绑定关系；同时管理 Template Material 的元数据
与适用分类。

**Why this priority**: 解析结果 rarely 一次到位；树编辑与素材管理是模板资产治理的
日常操作，直接影响后续模块组织建议质量。

**Independent Test**: 管理员在模板库中心打开某 Template 的章节树，拖拽或调整层级、
修改章节类型与产品分类后保存；刷新后结构保持一致；对 PPT、封面、攻略、Excel 类素材
可查看并编辑元数据与附件信息。

**Acceptance Scenarios**:

1. **Given** 已存在 Template 及章节树，**When** 管理员编辑章节标题、层级、排序、
   章节类型、产品分类或必填标记，**Then** 保存成功后树结构按人工编辑结果展示。
2. **Given** Template Chapter 含绑定素材、变量或规则引用，**When** 管理员查看章节详情，
   **Then** 可看到关联的 Template Material、变量与规则标识（只读或可编辑依字段类型）。
3. **Given** Template Material 为 PPT、封面、攻略或 Excel 类型，**When** 管理员管理素材，
   **Then** MVP 阶段至少支持元数据、附件引用与适用产品分类的维护，不要求语义生成能力。
4. **Given** 管理员对章节树做结构性变更，**When** 保存，
   **Then** 操作写入审计日志，且变更可追溯至操作者与时间。

---

### User Story 4 - 模板库管理与发布 (Priority: P3)

知识库管理员需要创建或选择 Template Library、将 Template 归入库中或保留为「未归类模板」，
配置模板变量与 MVP 规则，并在审核完成后发布 Template Library 或 Template，使已发布
资产参与后续模板推荐。

**Why this priority**: 发布门控保证只有经治理的模板进入推荐链路；模板库组织支撑
多模板集合管理，但可在解析与编辑能力就绪后交付。

**Independent Test**: 管理员创建 Template Library、将 Template 归入其中并配置至少一个
简单占位符变量与一条 MVP 规则，完成发布后，该库状态为已发布且参与模板推荐；未发布
状态的库不参与推荐。

**Acceptance Scenarios**:

1. **Given** 管理员需组织模板，**When** 创建 Template Library 或选择已有库，
   **Then** 可将 Template 归入该库，或选择「未归类模板」暂不归库。
2. **Given** Template 含占位符如 `{{project_name}}`，**When** 管理员配置 Template Variable，
   **Then** 可设置默认值与是否必填；变量定义随模板版本保留。
3. **Given** 管理员配置 Template Rule，**When** 选择 MVP 支持的规则类型
   （required、optional、product_match），**Then** 规则与 Template Chapter 关联并持久化。
4. **Given** 管理员完成模板结构与变量/规则审核，**When** 执行发布 Template Library
   或 Template，**Then** 资产状态变为已发布，保留版本信息、关联导入文件、作者与更新时间；
   且已发布库参与后续模板推荐，未发布库不参与。
5. **Given** 已发布 Template Library 存在历史版本，**When** 管理员查看版本信息，
   **Then** 可区分当前发布版本与历史版本，且已发布对象 MUST NOT 被物理删除，仅可废弃。

---

### Edge Cases

- 模板文档无清晰标题层级时，系统如何生成初始章节树？系统 MUST 生成扁平或最小层级
  结构并标记待人工整理，而非解析失败。
- 同一 File Import 重复触发解析时，系统 MUST 提示已有解析任务或结果，并允许重新处理
  而不破坏原 File Import。
- 解析过程中源文件被移动或不可读时，任务 MUST 标记失败并保留错误原因，File Import
  记录保持可查。
- 管理员将 Template 从未归类移至某 Template Library 后，原有关联导入文件与审计
  记录 MUST 保持连续。
- 发布前缺少必填变量默认值或必填章节未满足 required 规则时，系统 MUST 阻止发布并
  给出可操作的校验提示。
- 人工已确认的章节树与再次解析产生的结构不一致时，系统 MUST 生成待确认差异而非
  静默覆盖。
- 导入文件为超大文档（如数百页完整标书或资质合集）时，解析 MUST 先结构化切分为
  章节/素材块，再对每个块独立执行分类建议与 LLM 辅助；整文件 LLM 处理 MUST 被拒绝
  或自动拆批。
- Bid Outline 转换生成 Template 不在本 Epic 范围；若用户期望此路径，系统不在 MVP
  中提供该入口。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 仅对 File Import 已确认 `file_purpose = template_file` 的记录
  启动模板解析任务。
- **FR-002**: 系统 MUST 将模板文档标题结构解析为 Template 及其 Template Chapter 树，
  并依据文档内前缀数字确定章节排序。
- **FR-003**: 系统 MUST 从模板文档中提取固定段落、表格、图片等为 Template Material
  或 Candidate Knowledge 候选，并关联至对应章节或 Template。
- **FR-004**: 系统 MUST 基于文件名与文档标题，为产品分类与章节类型生成可覆盖的建议；
  该建议作用于解析产出的知识块（Template Chapter、Template Material、Candidate Knowledge），
  而非对导入文件本身做细粒度分类。导入文件可能是完整标书、标书模板、产品方案或资质合集，
  文件级仅保留 Epic 1 已确认的 `file_purpose`，不在本 Epic 重复细分文件类型。
- **FR-004a**: 系统 MUST 对 Candidate Knowledge 及关联章节/素材块执行产品分类、章节类型、
  知识类型等分类建议；人工确认界面以知识块为粒度展示与修正分类结果。
- **FR-005**: 系统 MUST 提供模板解析任务状态查询，且任务失败 MUST NOT 破坏或删除
  原 File Import 记录。
- **FR-006**: 系统 MUST 提供人工确认界面，支持确认或修正：Template Library 归类、
  产品分类、章节层级、章节类型、固定章节标记、KU/Wiki 提取意向及忽略标记。
- **FR-007**: 人工确认或编辑后的 Template Chapter 结构 MUST 优先于后续自动解析结果；
  再次解析仅可产生待确认差异，不得直接覆盖已确认结构。
- **FR-008**: 系统 MUST 支持 Template Library 的创建、查询与管理；一个库 MAY 包含
  多个 Template；MUST NOT 从文件夹自动生成 Template Library。
- **FR-009**: 系统 MUST 支持将 Template 归入已有 Template Library 或保留为
  「未归类模板」。
- **FR-010**: 系统 MUST 支持 Template Chapter 树的查看与编辑，包括标题、层级、排序、
  章节类型、产品分类、必填标记及与素材/变量/规则的关联展示。
- **FR-011**: 系统 MUST 支持 Template Material 的管理；对 PPT、封面、攻略、Excel 类
  素材，MVP 至少支持元数据、附件引用与适用产品分类。
- **FR-012**: 系统 MUST 支持 Template Variable 的配置，MVP 仅支持简单占位符替换
  （如 `{{project_name}}`），含默认值与必填标记。
- **FR-013**: 系统 MUST 支持 Template Rule 的 MVP 类型：required、optional、
  product_match；conditional、mutex、asset_required 不在 MVP 范围。
- **FR-014**: 系统 MUST 支持 Template Library 与 Template 的发布与版本管理；仅已发布
  的 Template Library 参与后续模板推荐。
- **FR-015**: 已发布的 Template、Template Library 及相关资产 MUST NOT 物理删除，
  仅可废弃（soft deprecate）。
- **FR-016**: Template Library MUST 保留关联导入文件、作者、更新时间与版本信息。
- **FR-017**: 模板解析、人工确认、编辑与发布操作 MUST 写入可追溯的审计日志。
- **FR-018**: 未确认或未发布的模板资产 MUST NOT 作为正式模板推荐或对外检索结果返回。
- **FR-019**: 系统 MUST 提供模板库中心，支持 Template Library 列表、Template 管理、
  章节树编辑、素材管理、变量与规则配置、发布与版本查看。
- **FR-020**: 系统 MUST NOT 在本 Epic 中实现：文件夹批量生成 Template Library、
  复杂变量表达式或脚本计算、完整 Template Instance 生成、招标约束驱动的章节草稿生成、
  Bid Outline 转 Template。
- **FR-021**: 凡需 LLM 辅助的步骤（如章节/素材块分类建议、摘要生成）MUST 通过可配置
  的 LLM 客户端调用；配置项包括 provider、api_key、base_url、model，均来自环境变量，
  支持在不改代码的情况下切换千问或其他 OpenAI 兼容提供商。
- **FR-022**: LLM 调用 MUST 以知识块为批次单位（章节节点、段落片段、Template Material
  等）；MUST NOT 将整份导入文件一次性送入模型。单块超出模型上下文上限时 MUST 进一步
  切分或截断并记录处理策略。
- **FR-023**: 未配置 `LLM_API_KEY` 或 LLM 调用失败时，系统 MUST 降级为规则/启发式
  建议并继续解析任务，MUST NOT 因 LLM 不可用而阻断模板解析主流程。

### Key Entities *(include if feature involves data)*

- **Template Library**: 一组相关标书模板的集合；含发布状态、版本、关联导入文件、
  作者与更新时间；发布后才参与模板推荐。
- **Template**: 可实例化的标书结构模板；包含多个 Template Chapter；可由模板文件
  解析生成；不等同于单个 docx 文件。
- **Template Chapter**: 模板中的章节节点；含层级、排序、章节类型、产品分类、
  必填标记，及与素材、变量、规则、知识绑定的关联。
- **Template Material**: 模板章节关联的原始素材文件或片段；可作为 KU 或 Wiki 的
  候选来源；MVP 对非文档类素材保留元数据与附件。
- **Template Variable**: 模板占位符；MVP 支持简单文本替换、默认值与必填约束；
  替换结果须可在后续生成快照中追溯（由下游 Epic 消费）。
- **Template Rule**: 模板章节治理规则；MVP 支持 required、optional、product_match。
- **Candidate Knowledge**: 解析过程中产生的待确认知识候选；经人工确认后由 Epic 4
  治理为正式 KU 或 Wiki。
- **Template Parse Task**: 模板文件解析异步任务；关联 File Import，含状态与错误信息。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理员可在单次操作链路内（上传确认 → 解析 → 人工确认）将一份标书模板
  文件转化为含章节树与素材列表的 Template，全流程可在 30 分钟内由熟练用户完成
  （不含大规模手工结构调整）。
- **SC-002**: 对含标准数字编号标题结构的模板文档，解析生成的章节树与文档标题层级
  一致率达到 90% 以上（以人工确认前自动结果计），且排序与编号顺序一致。
- **SC-003**: 100% 的模板解析失败场景保留完整 File Import 记录，且管理员可在
  同一导入记录上重新发起解析而无需重新上传文件。
- **SC-004**: 管理员可在模板库中心完成章节层级、章节类型、产品分类与排序编辑，
  保存后 100% 反映在用户再次打开的树视图中。
- **SC-005**: 未发布的 Template Library 在模板推荐场景中返回率为 0%；已发布库
  可被后续推荐流程检索到。
- **SC-006**: 所有模板解析、确认、编辑与发布操作均可通过审计日志关联至具体操作者与
  时间戳，满足 100% 关键操作可追溯。
- **SC-007**: 90% 的管理员可在首次使用时，在无额外培训情况下完成「解析 → 确认 →
  发布」主流程（以内部可用性走查计）。
- **SC-008**: 对超过 50MB 或超过 200 页的模板/标书类导入文件，解析任务 MUST 在
  合理时间内完成首批可确认知识块产出（分批 LLM），且不因整文件 LLM 调用导致 OOM
  或超时失败。

## Assumptions

- Epic 0（Product Category、Chapter Taxonomy）与 Epic 1（File Import 及
  `file_purpose = template_file` 确认）已可用；本 Epic 不重复实现导入与用途确认能力。
- 目标用户为知识库管理员或具备同等权限的内容治理人员；V3.0-MVP 暂不区分细粒度角色权限。
- 模板源文件主要为 docx；其他扩展名依文件类型选择解析策略，MVP 以 docx 为主路径，
  非 docx 文件解析深度以「可生成章节树或元数据」为下限。
- Template 由 Bid Outline 转换生成属于后续 Epic 或增强范围，本 Epic 仅覆盖
  「File Import → 模板解析」主路径。
- 模板变量替换结果写入生成快照的具体机制由 Epic 6 消费；本 Epic 仅保证变量定义
  与版本随模板发布持久化。
- Candidate Knowledge 的正式发布流程由 Epic 4 负责；本 Epic 仅产生并传递候选。
- 模板库在 V3.0 中是知识来源与模块组织建议来源，不是最终标书结构的最高约束；
  招标约束优先级高于模板建议（与 Constitution 一致）。
- 「未归类模板」为有效中间状态，允许 Template 暂不归入任何 Template Library，
  直至管理员完成归类或发布决策。
- 导入文件类型多样（完整标书、标书模板、产品方案、资质合集等）；Epic 1 的
  `file_purpose` 为文件级粗粒度用途，本 Epic 的细粒度分类（产品分类、章节类型、
  知识类型）均在解析后的知识块上执行。
- LLM 为可选增强能力：默认 provider 为千问（Qwen），通过环境变量切换；无 Key 时
  全流程仍可用规则引擎完成解析与建议。
- 大文件处理假设：先 docx/文档结构解析得到章节树与素材块，再按块调度 LLM；
  不存在「整文件一次 LLM」的设计路径。

## Dependencies

- **Epic 0**: Product Category、Chapter Taxonomy 分类底座。
- **Epic 1**: File Import、文件用途确认为 `template_file`、导入审计与存储。
- **Epic 4**（下游）: 接收 Candidate Knowledge 候选。
- **Epic 5**（下游）: 检索 Template Chapter、Template Material 作为模块建议来源。
- **Epic 6**（下游）: 使用 Template Chapter、变量与规则参与生成辅助。
