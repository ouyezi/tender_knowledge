# Feature Specification: Epic 4 候选知识确认工作台

**Feature Branch**: `006-candidate-confirm-workbench`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "docs/epics/epic4-候选知识确认工作台.md"

**Source**: `docs/epics/epic4-候选知识确认工作台.md` · `docs/总需求.md` §6.15、§8.4、§12、§15.5、§16.3、§17、§18 Phase 3 后半、§19.2、§20、§22

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 浏览与筛选待确认候选知识 (Priority: P1)

知识库管理员需要在一个集中工作台查看由导入批次产生的 Candidate Knowledge 列表，
并按导入批次、产品分类、章节类型、候选类型、状态等维度筛选，以便优先处理高价值或
高置信度候选。

**Why this priority**: 列表与筛选是确认工作流的入口；无此能力，管理员无法定位待处理
候选，治理闭环无法启动。

**Independent Test**: 管理员打开候选知识中心，看到来自 Epic 2/3 的候选列表；应用
筛选条件后列表仅展示匹配项；点击任一候选可进入详情。

**Acceptance Scenarios**:

1. **Given** 系统中存在由模板解析或实际标书解析生成的 Candidate Knowledge，
   **When** 管理员打开候选知识列表，
   **Then** 可查看每条候选的标题、候选类型、建议知识类型、置信度、状态及关联导入批次。
2. **Given** 候选知识列表已展示，**When** 管理员按导入批次、产品分类、章节类型、
   候选类型或状态筛选，
   **Then** 列表仅展示满足全部所选条件的候选。
3. **Given** 管理员查看候选列表，**When** 尝试通过正式知识检索或对外服务接口查询，
   **Then** 未确认候选知识 MUST NOT 出现在检索结果或对外可用知识中。
4. **Given** 同一导入批次产生多条候选，**When** 管理员按批次筛选，
   **Then** 可一次性定位该批次下全部待确认项。

---

### User Story 2 - 查看与编辑候选详情 (Priority: P1)

知识库管理员需要查看单条候选的完整内容与来源链，并编辑标题、摘要、正文及分类建议，
为发布决策做准备。

**Why this priority**: 人工确认的核心是审阅与修正机器产出；编辑能力直接决定发布资产
的准确性与可用性。

**Independent Test**: 管理员打开一条候选详情，修改标题与摘要并保存；刷新后变更持久化；
详情页可查看来源文档、来源节点及建议分类字段。

**Acceptance Scenarios**:

1. **Given** 管理员选中一条 Candidate Knowledge，**When** 打开详情，
   **Then** 可查看标题、摘要、正文、候选类型、建议知识类型、建议章节类型、
   建议产品分类、置信度、状态及来源链（导入批次、来源文档、来源节点）。
2. **Given** 候选处于待确认状态，**When** 管理员编辑标题、摘要或正文并保存，
   **Then** 变更持久化且更新时间反映最新编辑。
3. **Given** 候选含建议分类信息，**When** 管理员修正产品分类或章节类型建议，
   **Then** 修正结果保存成功，且作为后续发布时的默认确认值。
4. **Given** 候选已被忽略或已发布，**When** 管理员尝试编辑，
   **Then** 系统按终态规则限制或禁止不当修改，并给出明确提示。

---

### User Story 3 - 将候选发布为正式知识资产 (Priority: P1)

知识库管理员在审阅并确认必要字段后，需要将候选发布为正式 KU、Wiki、Template Chapter、
Manual Asset、Chapter Pattern 或 Product Category，且发布后保留来源追溯。

**Why this priority**: 发布是 Epic 4 的治理闭环终点；Epic 5/6 仅可使用已发布资产，
本故事直接交付平台核心价值。

**Independent Test**: 管理员选择一条候选，确认入库对象类型及分类字段后执行发布；
发布成功后可在对应正式资产区查看新对象，且该对象可追溯到原 candidate_id。

**Acceptance Scenarios**:

1. **Given** 管理员已审阅候选详情，**When** 确认入库对象类型、标题、摘要、产品分类、
   章节类型、知识类型、推荐使用方式、是否可检索及来源链后执行发布，
   **Then** 系统按映射规则创建对应正式对象：
   Candidate KU → Knowledge Unit；Candidate Wiki → Wiki；
   Candidate Template Chapter → Template Chapter；
   Candidate Manual Asset → Manual Asset；
   Candidate Chapter Pattern → Chapter Pattern；
   Candidate Product Category → Product Category。
2. **Given** 发布成功，**When** 管理员查看新创建的正式对象，
   **Then** 正式对象保留对原 candidate_id 的来源引用，且候选状态更新为已发布。
3. **Given** 发布所需字段不完整或来源链校验失败，**When** 管理员尝试发布，
   **Then** 系统阻止发布并说明缺失或冲突项。
4. **Given** 发布过程因临时故障失败，**When** 管理员重试发布，
   **Then** 可在不破坏源候选与已存在源文件记录的前提下完成发布或再次失败并保留
   可重试状态。
5. **Given** 候选被发布为需版本管理的对象类型（KU、Wiki、Template Chapter、
   Chapter Pattern 等），**When** 发布完成，
   **Then** 新对象以初始版本入库，且已发布对象 MUST NOT 被物理删除，仅可废弃。

---

### User Story 4 - 合并、拆分与忽略候选 (Priority: P2)

知识库管理员需要对重复、碎片化或低价值候选执行合并、拆分或忽略，以保持候选区整洁
并避免重复发布。

**Why this priority**: 机器生成的候选常存在冗余或粒度不当；治理操作是确认工作台的
必要能力，但可在单条发布能力可用后交付。

**Independent Test**: 管理员将两条相似候选合并为一条、或将一条候选拆分为两条、
或将无效候选标记为忽略；操作后候选列表与状态符合预期，且操作可追溯。

**Acceptance Scenarios**:

1. **Given** 多条内容相近的 Candidate Knowledge 处于待确认状态，
   **When** 管理员执行合并，
   **Then** 生成或保留一条合并后的候选，被合并项按规则归档或标记，且来源链信息
   不丢失。
2. **Given** 一条候选包含多个可独立发布的知识片段，
   **When** 管理员执行拆分，
   **Then** 生成多条独立候选，各自保留适当的来源与分类建议。
3. **Given** 管理员判定某候选无入库价值，
   **When** 执行忽略（confirm_as = ignore），
   **Then** 候选状态更新为已忽略，且 MUST NOT 进入正式检索或生成流程。
4. **Given** 管理员执行合并、拆分或忽略，
   **When** 操作完成，
   **Then** 操作写入审计日志，包含操作者、时间、影响候选及结果摘要。

---

### User Story 5 - 批量确认与批量驳回 (Priority: P2)

知识库管理员需要对一批已通过预审的候选执行批量确认发布，或对明显无效候选执行批量
驳回，以提高处理效率。

**Why this priority**: 导入批次常产生大量候选；批量操作显著降低人工成本，但依赖
单条确认规则已稳定可用。

**Independent Test**: 管理员多选候选后执行批量确认或批量驳回；系统逐条或按批次规则
处理并记录审计日志；失败项可单独查看原因并重试。

**Acceptance Scenarios**:

1. **Given** 管理员在列表中多选若干待确认候选且均满足发布前置条件，
   **When** 执行批量确认，
   **Then** 系统按各候选确认的入库类型与分类信息逐条发布，并汇总成功与失败结果。
2. **Given** 管理员多选若干无效候选，
   **When** 执行批量驳回，
   **Then** 候选状态更新为已忽略或已驳回，且 MUST NOT 泄露至正式知识区。
3. **Given** 批量操作中部分条目失败，
   **When** 操作完成，
   **Then** 成功项正常入库或更新状态，失败项保持可重试状态并展示失败原因。
4. **Given** 任意批量确认或批量驳回完成，
   **When** 审计人员查看操作日志，
   **Then** 可看到批次级操作记录及受影响候选清单。

---

### User Story 6 - 查看确认操作日志 (Priority: P3)

知识库管理员或审计人员需要查看候选确认、发布、合并、拆分、忽略及批量操作的日志，
以支撑问题排查与合规审计。

**Why this priority**: 审计是治理闭环的保障，但不阻塞核心确认与发布路径。

**Independent Test**: 管理员完成若干确认操作后，在操作日志页按时间或候选筛选；
可看到对应操作类型、操作者、时间及关联 candidate_id。

**Acceptance Scenarios**:

1. **Given** 系统已记录候选相关操作，
   **When** 管理员打开操作日志视图，
   **Then** 可查看发布、忽略、合并、拆分、批量确认、批量驳回等操作记录。
2. **Given** 操作日志列表已展示，
   **When** 按候选、导入批次或时间范围筛选，
   **Then** 仅展示匹配的操作记录。
3. **Given** 某次发布失败后被重试成功，
   **When** 查看该候选的操作日志，
   **Then** 可看到失败与成功两次尝试的可区分记录。

---

### Edge Cases

- 当同一来源节点产生多条类型不同的候选时，管理员应能分别确认或合并，且来源链
  指向正确节点。
- 当候选建议的产品分类或章节类型已被废弃时，发布前应提示管理员重新选择有效分类。
- 当候选处于发布进行中状态时，重复提交发布或批量操作应被幂等处理或明确拒绝。
- 当合并目标候选已被发布或忽略时，合并操作应失败并说明原因。
- 当拆分后子候选缺少必要分类建议时，系统应允许管理员补全后再发布。
- 当 Epic 2/3 尚未产生任何候选时，列表应展示空状态而非错误。
- 当发布创建正式对象成功但更新候选状态失败时，系统应支持重试且不得产生无法追溯
  的重复正式对象。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供 Candidate Knowledge 列表，展示标题、候选类型、状态、
  置信度、关联导入批次及关键建议字段。
- **FR-002**: 系统 MUST 支持按导入批次、产品分类、章节类型、候选类型、状态筛选
  候选列表。
- **FR-003**: 系统 MUST 提供候选详情视图，展示正文、摘要、来源链及全部建议分类字段。
- **FR-004**: 系统 MUST 允许管理员编辑待确认候选的标题、摘要、正文及分类建议，并
  持久化变更。
- **FR-005**: 系统 MUST 支持将候选发布为以下正式对象之一：Knowledge Unit、Wiki、
  Template Chapter、Manual Asset、Chapter Pattern、Product Category。
- **FR-006**: 系统 MUST 在发布前校验入库对象类型、标题、摘要、产品分类、章节类型、
  知识类型、推荐使用方式、是否可检索及来源链完整性；校验失败时 MUST 阻止发布。
- **FR-007**: 系统 MUST 在发布成功后保留 candidate_id 作为正式对象的来源引用，并
  更新候选状态为已发布。
- **FR-008**: 系统 MUST 支持将候选标记为忽略，被忽略候选 MUST NOT 进入正式检索或
  生成流程。
- **FR-009**: 系统 MUST 支持候选合并与拆分，且合并、拆分后来源信息 MUST 可追溯到
  原始导入与文档节点。
- **FR-010**: 系统 MUST 支持批量确认与批量驳回，并返回逐条成功与失败结果。
- **FR-011**: 系统 MUST 为发布、忽略、合并、拆分、批量确认、批量驳回及编辑操作
  记录审计日志，日志 MUST 包含可追溯的操作标识。
- **FR-012**: 系统 MUST 支持 Candidate Knowledge 发布失败后的重试，且重试 MUST NOT
  破坏已存在的源文件记录或产生不可追溯的重复正式对象。
- **FR-013**: Candidate Knowledge MUST 默认不参与正式检索；未确认候选 MUST NOT
  通过对外知识服务或检索接口泄露。
- **FR-014**: 系统 MUST 提供候选确认能力的服务接口，接受确认目标类型、分类信息与
  审阅备注，并返回确认后的对象类型、对象标识、状态及可追溯标识。
- **FR-015**: 已发布的 KU、Wiki、Template Chapter、Chapter Pattern 等需版本管理
  的对象 MUST NOT 被物理删除，仅支持废弃（soft deprecate）。
- **FR-016**: Candidate Template Chapter 与 Candidate Product Category MUST 统一
  通过 Candidate Knowledge 的候选类型表达，MUST NOT 单独建立并行候选实体表对外暴露。
- **FR-017**: 系统 MUST NOT 在本功能范围内提供实际标书解析、模板解析、正式检索
  策略优化、双人审核或复杂权限流。

### Key Entities *(include if feature involves data)*

- **Candidate Knowledge**: 待人工确认的候选知识，关联知识库、导入批次、来源文档与
  来源节点；含候选类型、标题、摘要、正文、建议分类、置信度、状态，以及确认后指向的
  正式对象类型与标识。
- **Confirmed Knowledge Asset**: 经人工确认发布的正式对象，类型包括 Knowledge Unit、
  Wiki、Template Chapter、Manual Asset、Chapter Pattern、Product Category；保留
  对 candidate_id 的来源引用，并遵循版本与废弃规则。
- **Import Batch**: 产生候选的导入记录，用于列表筛选与批次级批量操作。
- **Confirmation Audit Log**: 记录确认、发布、忽略、合并、拆分、批量操作及失败
  重试的结构化审计条目，可关联 candidate_id、操作者与 trace 标识。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理员可在 3 分钟内从候选列表定位到指定导入批次的全部待确认项并完成
  筛选。
- **SC-002**: 95% 的单条候选从打开详情到完成发布（含字段确认）可在 5 分钟内完成。
- **SC-003**: 100% 成功发布的正式对象均可通过 candidate_id 追溯到原始候选与来源
  导入链。
- **SC-004**: 未确认候选在正式检索与对外知识接口中的泄露率为 0（验收抽样 100% 通过）。
- **SC-005**: 发布失败后，管理员可在不重新导入源文件的情况下于 2 次重试内完成发布
  或获得明确失败原因。
- **SC-006**: 批量确认 50 条候选时，操作结果汇总（成功/失败清单）在操作完成后 30
  秒内可供查看。
- **SC-007**: 所有批量确认、批量驳回、发布与忽略操作 100% 可在审计日志中按 candidate_id
  或批次检索到。

## Assumptions

- 目标用户为知识库管理员；V3.0-MVP 不实现角色级权限分流，所有管理操作由同一管理员
  角色执行，但仍记录操作者标识以满足审计要求。
- Epic 0（Product Category、Chapter Taxonomy）与 Epic 2 或 Epic 3 已完成，系统中
  已存在可确认的 Candidate Knowledge。
- 候选区与正式区在数据与检索边界上隔离；Epic 5 检索与 Epic 6 生成辅助将仅消费
  本 Epic 发布后的正式对象。
- 双人审核、复杂审批流、正式检索策略调优不在本 Epic 范围内。
- 发布失败重试采用幂等语义：同一 candidate_id 的重复成功发布不得创建多个不可关联
  的正式对象。
- Bid Outline 历史版本在 MVP 阶段以操作日志记录为主，不要求完整版本树 UI。

## Dependencies

- **Epic 0**：分类底座（Product Category、Chapter Taxonomy）可用。
- **Epic 2 或 Epic 3**：已产生 Candidate Knowledge 及关联来源元数据。
- **下游 Epic 5 / Epic 6**：依赖本 Epic 发布的正式知识资产；本规格不实现检索或
  生成辅助本身。

## Out of Scope

- 实际标书解析与 Bid Outline 抽取（Epic 3）。
- 模板解析与模板候选生成（Epic 2）。
- 正式知识检索策略与召回优化（Epic 5）。
- 模块组织建议与生成辅助（Epic 6）。
- 双人审核、多级审批及细粒度权限模型。
