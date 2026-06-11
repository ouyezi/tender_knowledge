# Feature Specification: Epic 1 来源导入与文件分类确认

**Feature Branch**: `002-source-import-classify`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: "Epic 1 docs/epics/epic1-来源导入与文件分类确认.md"

**Source**: `docs/epics/epic1-来源导入与文件分类确认.md` · `docs/总需求.md` §5、§14、§15.1、§16.1、§17、§18 Phase 1、§19.1、§19.2、§20、§22

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 单文件上传与导入记录 (Priority: P1)

知识库管理员需要将单个来源文件（如 docx、pdf、ppt、xlsx、图片）上传到平台，
系统立即创建可追溯的导入记录并返回导入标识，作为后续分类确认与分流的起点。

**Why this priority**: 单文件导入是 V3.0-MVP 第一个业务闭环的入口；无 File Import
记录则无法开展用途识别、人工确认与后续 Epic 2/3 解析链路。

**Independent Test**: 管理员在来源导入中心上传一个支持的文件，系统在数秒内返回
导入标识；管理员可在导入列表中查看文件名、大小、状态与创建时间，无需完成分类确认
即可验证上传与记录创建能力。

**Acceptance Scenarios**:

1. **Given** 管理员已选定目标知识库，**When** 上传单个 docx 文件，
   **Then** 系统创建 File Import 记录，快速返回导入标识，且记录含文件名、类型、
   大小、存储位置与「待确认」类状态。
2. **Given** 管理员上传 pdf、ppt、xlsx 或图片文件各一次，
   **When** 每次上传完成，**Then** 均成功创建独立 File Import 记录，且文件类型
   被正确识别。
3. **Given** 文件上传进行中，**When** 上传失败（网络中断、文件过大、格式不支持），
   **Then** 系统给出明确错误提示，且不产生不完整或不可追溯的导入记录。
4. **Given** 上传成功，**When** 管理员查看导入列表，
   **Then** 可按知识库浏览所有 File Import，并查看每条记录的处理状态。

---

### User Story 2 - 用途建议与人工确认 (Priority: P2)

知识库管理员在文件导入后，需要查看系统对文件用途、产品分类和章节类型的自动建议，
并人工确认或覆盖后保存，再决定是否进入解析及目标对象类型。

**Why this priority**: 人工确认门是 V3.0 核心治理原则；自动建议仅作辅助，确认结果
决定后续分流路径，是连接「收文件」与「进解析」的关键环节。

**Independent Test**: 管理员打开一条已上传的 File Import，查看系统建议的用途、
产品分类与章节类型，修改其中任意字段并保存；保存后记录状态反映已确认，且人工选择
优先于系统建议。

**Acceptance Scenarios**:

1. **Given** 新创建的 File Import，**When** 系统完成基础信息计算，
   **Then** 展示文件用途建议（如 actual_bid、template_file、qualification 等）、
   产品分类建议与章节类型建议，且文件名 MAY 作为推断辅助信息。
2. **Given** 管理员查看建议结果，**When** 将文件用途改为与建议不同的值并选择
   目标产品分类与章节类型，**Then** 保存成功，且以人工确认值为准持久化。
3. **Given** 管理员确认文件用途，**When** 选择「忽略」或设定不进入解析，
   **Then** 记录标记为已忽略，保留导入日志，且不触发后续解析任务。
4. **Given** 管理员确认时选择目标对象类型（Document、Template Material、
   Manual Asset、Wiki 或忽略），**When** 保存确认，
   **Then** 目标对象类型与文件用途一并记录，供分流使用。
5. **Given** File Import 尚未完成用途确认，**When** 系统检查任务队列，
   **Then** 该文件 MUST NOT 进入任何后续解析任务。

---

### User Story 3 - 分流、去重与失败重试 (Priority: P3)

知识库管理员在确认文件用途后，需要系统按用途自动创建对应后续任务；对重复文件
可选择跳过或作为新版本导入；对失败导入可重新处理并查看任务日志。

**Why this priority**: 分流与去重保证平台不重复劳动、链路清晰；任务日志与重试支撑
可观测性与可恢复性，是 MVP 闭环可持续运行的保障。

**Independent Test**: 管理员依次确认不同 file_purpose 的文件并保存；系统为每种用途
创建对应类型的后续任务；对同一 hash 的重复上传，系统提示重复并允许跳过或新版本导入；
对失败记录执行重新处理并查看日志。

**Acceptance Scenarios**:

1. **Given** 管理员确认 file_purpose 为 actual_bid，**When** 保存确认，
   **Then** 系统创建面向 Document 解析、Bid Outline 抽取与 Candidate Knowledge
   生成的后续任务（具体解析由 Epic 3 消费，本 Epic 仅负责创建任务入口）。
2. **Given** 管理员确认 file_purpose 为 template_file，**When** 保存确认，
   **Then** 系统创建 Template / Template Chapter / Template Material 解析任务入口
   （由 Epic 2 消费）。
3. **Given** 管理员确认 file_purpose 为 qualification、ppt_material、cover_guide、
   writing_guide、wiki_source 或 other，**When** 保存确认，
   **Then** 系统按 epic 定义的分流规则创建对应候选流程任务或标记为附件/忽略，
   且 other 默认不自动进入知识生产。
4. **Given** 上传文件与已有 File Import 的 file_hash 相同，**When** 系统检测重复，
   **Then** 提示重复并默认不重复解析，且管理员可选择「跳过」或「作为新版本导入」。
5. **Given** 无法计算 file_hash 的文件，**When** 系统执行去重判断，
   **Then** 使用 file_name + file_size 作为辅助判断依据。
6. **Given** File Import 处于未处理或处理失败状态，**When** 管理员发起重新处理，
   **Then** 系统允许重试且任务日志可查看；已发布对象 MUST NOT 被物理删除，
   仅可走废弃流程。
7. **Given** 任意 file_import 或 file_purpose_classify 任务执行，
   **When** 管理员在任务中心查看，**Then** 可查看任务日志且结果可追溯到对应
   File Import；失败任务支持重试。

---

### Edge Cases

- 上传空文件或零字节文件：系统拒绝并提示，不创建 File Import。
- 上传不支持格式的文件：系统在上传前或上传时拒绝，并列出支持的格式范围。
- 超大文件超出平台限制：上传失败并提示大小限制，不产生半成品记录。
- file_hash 计算失败：降级使用 file_name + file_size 去重，并在记录中标记 hash 不可用。
- 重复文件选择「作为新版本导入」：创建新 File Import 记录，与旧记录通过 hash 或
  版本关系可追溯，且允许独立确认与分流。
- 用途确认保存时产品分类或章节类型已被停用：系统提示不可选分类，要求重新选择启用中项。
- 并发对同一 File Import 确认：后保存者覆盖或系统提示冲突（以 plan 阶段确定策略）；
  本 spec 要求至少保证数据一致、操作可审计。
- 确认后下游任务创建失败：File Import 保留已确认状态，任务标记失败并可重试，
  不得回滚已确认的分类结果。
- 被忽略文件再次打开：管理员可查看历史确认与忽略原因，但默认不自动重新进入解析。
- 重导入场景下存在未发布 Candidate Knowledge：允许删除或标记 rejected；
  已发布对象仅允许废弃，不允许物理删除。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 支持单文件上传，每次上传创建一条 File Import 记录；
  MUST NOT 在本 Epic 实现目录导入、文件夹扫描或批量导入。
- **FR-002**: File Import MUST 包含：import_id、kb_id、file_name、file_type、
  file_size、file_hash（可空）、storage_path、file_purpose（确认前可空）、
  product_category_ids、chapter_taxonomy_id、status、created_by、created_time、
  updated_time。
- **FR-003**: file_purpose 枚举 MUST 支持：actual_bid、template_file、qualification、
  ppt_material、cover_guide、writing_guide、wiki_source、other。
- **FR-004**: 上传完成后系统 MUST 快速返回 File Import 标识，使用户无需等待
  完整解析即可进入确认流程。
- **FR-005**: 系统 MUST 在导入后计算文件基础信息（含 file_hash，若可计算）并
  给出文件用途、产品分类、章节类型的自动建议。
- **FR-006**: 自动建议 MAY 使用文件名与内容摘要辅助推断；用户人工确认结果 MUST
  优先于机器建议并持久化。
- **FR-007**: 文件导入后 MUST 进入用途确认流程；用途确认完成前 MUST NOT 进入
  后续解析任务。
- **FR-008**: 用途确认时用户 MUST 可设置：文件用途、产品分类、章节类型、
  是否进入解析、目标对象类型（Document、Template Material、Manual Asset、Wiki、忽略）。
- **FR-009**: 被忽略或不进入解析的文件 MUST 保留导入日志，且 MUST NOT 创建解析任务。
- **FR-010**: 用途确认保存后，系统 MUST 按 file_purpose 分流规则创建对应后续
  处理任务入口（actual_bid → Document/Bid Outline/Candidate Knowledge 链路；
  template_file → Template 解析链路；qualification → Manual Asset 候选；
  ppt_material/cover_guide/writing_guide → Template Material 或素材元数据；
  wiki_source → Wiki 候选；other → 附件或忽略，不自动知识生产）。
- **FR-011**: 去重 MUST 优先使用 file_hash；hash 不可用时 MUST 使用
  file_name + file_size 辅助判断。
- **FR-012**: 重复文件默认 MUST NOT 重复解析；用户 MUST 可选择跳过或作为新版本导入。
- **FR-013**: 未处理或处理失败的 File Import MUST 支持重新处理；失败 MUST NOT
  破坏已存在的源文件记录。
- **FR-014**: 已发布对象 MUST NOT 物理删除；重导入时未发布 Candidate Knowledge
  MAY 删除或标记 rejected。
- **FR-015**: 系统 MUST 提供 file_import 与 file_purpose_classify 任务类型；
  任务 MUST 支持日志查看、结果追溯到 File Import、失败重试。
- **FR-016**: 来源导入中心（管理后台）MUST 支持：单文件上传、File Import 列表、
  处理状态查看、导入任务日志、用途人工确认、忽略文件、失败导入重新处理。
- **FR-017**: 系统 MUST 提供 File Import 相关能力：上传单个文件、查询导入状态；
  以及 File Purpose Confirm 相关能力：确认用途、分类与目标对象。
- **FR-018**: 系统 MUST 记录导入、确认、分流、重试等操作的审计信息，且日志 MUST
  可关联 trace，满足全链路可追溯原则。
- **FR-019**: 系统 MUST NOT 在本 Epic 实现：模板文件实际解析、标书目录抽取、
  候选知识生成与确认工作台、招标文件完整解析。
- **FR-020**: 产品分类与章节类型选项 MUST 来自 Epic 0 分类底座（启用中分类）；
  本 Epic MUST NOT 维护平行分类字典。

### Key Entities

- **File Import**: 一次单文件导入操作的业务记录；承载文件元数据、用途确认结果、
  处理状态与分流去向；是后续 Document/Template 解析链路的统一入口。
- **File Purpose Suggestion**: 系统对单次导入给出的用途、产品分类、章节类型建议
  集合；确认前展示，确认后以人工结果为准。
- **Import Task**: 任务中心中的 file_import（上传与基础处理）与
  file_purpose_classify（建议生成与确认相关）任务；含状态、日志与重试信息。
- **Downstream Task Entry**: 用途确认后按 file_purpose 创建的后续任务占位或
  调度记录；由 Epic 2/3 等消费，本 Epic 负责创建与状态可查询。
- **Knowledge Base**: File Import 的隔离单位；所有导入与确认在单一知识库范围内生效。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可在 2 分钟内完成「上传单个支持格式文件并获取导入标识」，
  且导入列表中可查到该记录。
- **SC-002**: 上传完成后，用户在 5 秒内获得 File Import 标识（无需等待完整解析）。
- **SC-003**: 对 docx、pdf、ppt、xlsx、图片五类文件，上传成功率在常规网络环境下
  达到 95% 以上（排除用户侧格式/大小违规）。
- **SC-004**: 系统对 80% 以上带典型文件名的样本文件，能给出至少一项可辨别的
  用途或分类建议（供人工确认，不要求自动准确率达标）。
- **SC-005**: 用途确认保存操作，95% 在 1 秒内完成响应（P95 < 1 秒）。
- **SC-006**: 用途确认后，100% 按 file_purpose 创建对应类型的后续任务入口
  （忽略类除外）；被忽略文件 0% 误入解析任务。
- **SC-007**: 相同 file_hash 的重复上传，100% 被识别并呈现跳过/新版本选项。
- **SC-008**: 失败导入重新处理后，管理员可在任务中心 100% 追溯到对应 File Import
  及任务日志。
- **SC-009**: Epic 2 可消费 template_file 分流结果，Epic 3 可消费 actual_bid
  分流结果（以集成验收时任务入口可查询、状态正确为准）。

## Assumptions

- Epic 0（产品分类与章节分类底座）已交付并可查询启用中的分类树与章节类型。
- 目标用户为知识库管理员或运营人员；V3.0 暂不区分细粒度角色权限，与 constitution
  及总需求 §3 一致。
- 单文件导入为唯一导入模式；目录/文件夹批量导入明确排除在 MVP 外。
- 支持的文件类型至少包括：docx、pdf、ppt（或 pptx）、xlsx、常见图片格式；
  具体大小上限在 plan 阶段按基础设施约束确定。
- 后续解析、候选知识生成、人工确认工作台由 Epic 2/3/4 实现；本 Epic 仅创建
  任务入口并保证状态可查询，不执行实际模板或标书正文解析。
- 知识库（Knowledge Base）已存在；上传时用户已选定目标 kb_id。
- LLM 或规则引擎可用于生成用途与分类建议，但输出仅作为建议进入确认页，
  不得静默写入正式用途字段。
- 加密存储与敏感文件审计遵循平台统一安全基线；本 Epic 复用既有存储与审计能力。
- 「作为新版本导入」与旧版本的关系在 plan 阶段定义具体字段（如 parent_import_id
  或 version_no），本 spec 要求行为可追溯、可独立确认。
