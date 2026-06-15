# Feature Specification: 实际标书解析接入 doc_chunk

**Feature Branch**: `009-doc-chunk-integration`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "tender_skills 已经按照要求修复并验证完毕，改造本项目代码"

**Source**: `tender_skills` doc_chunk 集成规格（002/003）· Epic 3 实际标书导入与候选知识 · `docs/总需求.md` §6.1–6.3、§6.10–6.15

**Depends on**: 外部包 `doc_chunk`（`tender_skills`）已完成锚点分块、文档树、linkage、blocks_v1 等能力并通过验证

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 实际标书解析结果与改造前一致 (Priority: P1)

知识库管理员对已确认 `file_purpose = actual_bid` 的 Word 标书发起解析后，系统应继续
产出可用的 Document、Document Tree、Bid Outline 与候选知识，且确认向导中的目录条数、
候选条数与章节正文与改造前处于同一量级，不出现「有目录无正文」或整篇合并为一条候选
的明显退化。

**Why this priority**: 解析结果是 Epic 3 全链路的起点；若切片或目录与正文错位，后续
目录确认、候选确认与检索均不可用。

**Independent Test**: 对同一份标准测试标书（含无 Word 标题样式、含大量图片的样例）分别
在改造前后完成解析；对比 Document Tree 节点数、Bid Outline 条目数、候选知识条数及
抽样章节正文是否含段落/表格/图片。

**Acceptance Scenarios**:

1. **Given** 已确认的实际标书 Word 文件，**When** 管理员启动解析，**Then** 解析任务
   成功完成且 Document 状态为可进入确认向导。
2. **Given** 标书无内置 Word 标题样式、靠编号分章，**When** 解析完成，**Then** 投标
   目录条目数与章节候选条数同量级（差异在可接受比例内，不因切片失败而仅产生极少数候选）。
3. **Given** 章节含嵌入图片，**When** 管理员在候选详情查看正文，**Then** 正文块中
   可展示图片（与改造前富文本体验一致）。
4. **Given** 解析执行中，**When** 管理员查看任务进度，**Then** 可见阶段性进度信息
   （如提取、目录、分块等），不出现长时间无反馈。

---

### User Story 2 - 目录确认向导无感知切换 (Priority: P1)

知识库管理员在实际标书解析完成后，应能沿用现有「解析确认向导」完成项目名称、客户名称、
产品分类、目录树浏览与候选列表确认，无需学习新流程或新页面。

**Why this priority**: Constitution 要求人工确认门；向导是 Epic 3 与 Epic 4 的衔接点，
改造不得破坏已交付的确认体验。

**Independent Test**: 解析完成后打开 Actual Bid Parse Confirm Wizard；完成各步骤提交确认；
验证 Bid Outline、候选列表、文档节点统计与 API 契约未破坏。

**Acceptance Scenarios**:

1. **Given** 解析任务 `ready` 且已生成 `bid_outline_id`，**When** 管理员打开确认向导，
   **Then** 可加载目录节点、候选列表与文档节点数量。
2. **Given** 管理员在向导中修改产品分类或章节映射，**When** 提交确认，
   **Then** 行为与改造前一致，审计与持久化规则不变。
3. **Given** Bid Outline 曾被人工锁定，**When** 用户强制重新解析，
   **Then** 仍仅生成结构差异建议，不得静默覆盖已确认目录（Constitution III）。

---

### User Story 3 - 候选知识正文与溯源完整 (Priority: P1)

知识库管理员在候选知识中心查看解析产出的待确认条目时，每条候选应包含完整章节正文
（段落、表格、图片引用），并可追溯到来源文件、Document 与来源章节节点。

**Why this priority**: 候选知识是 Epic 3 面向 Epic 4 的核心交付；正文质量决定确认效率。

**Independent Test**: 解析后列出 `pending` 候选；抽样检查 `content` 为结构化正文；
打开来源可关联到 Document Tree 对应 heading 节点。

**Acceptance Scenarios**:

1. **Given** 某投标目录节点对应有效章节内容，**When** 候选生成完成，
   **Then** 存在对应 Candidate Knowledge，标题与目录节点一致或可追溯。
2. **Given** 候选正文含表格与图片，**When** 在前端查看详情，
   **Then** 表格与图片按既有 blocks 格式渲染。
3. **Given** 章节类型规则判定为 `ignore`，**When** 候选生成完成，
   **Then** 不生成该章节的待确认候选（与既有规则一致）。
4. **Given** 管理员查看候选来源，**When** 打开溯源信息，
   **Then** 可关联 File Import、Document 与 `source_node_id` 对应节点。

---

### User Story 4 - 模板标书解析路径不受影响 (Priority: P2)

知识库管理员对 `file_purpose = template` 的模板标书进行解析时，系统应继续使用既有
模板解析逻辑（固定段落素材、变量检测等），不受本次实际标书改造影响。

**Why this priority**: 明确范围边界，避免一次改造波及其他 Epic 2 交付物。

**Independent Test**: 对模板文件触发模板解析任务；验证 Template Chapter、固定段落
素材与既有 API 行为不变。

**Acceptance Scenarios**:

1. **Given** File Import 用途为 `template`，**When** 启动模板解析，
   **Then** 不经过 doc_chunk 实际标书适配路径。
2. **Given** 模板解析完成，**When** 查看解析建议，
   **Then** 仍包含章节树与固定段落素材等既有字段。

---

### User Story 5 - 可回退与可观测 (Priority: P2)

平台运维或开发者在 doc_chunk 集成出现问题时，应能通过配置切换回既有解析实现，
并在日志与任务详情中区分解析策略，便于问题定位与回归对比。

**Why this priority**: 大型标书解析是关键路径；需要安全发布与快速回退手段。

**Independent Test**: 开启/关闭集成开关各执行一次解析；任务元数据或日志可识别所用策略；
关闭开关时行为与改造前一致。

**Acceptance Scenarios**:

1. **Given** 集成开关关闭，**When** 执行实际标书解析，
   **Then** 使用改造前内置解析逻辑，结果符合既有契约测试基线。
2. **Given** 集成开关开启，**When** 执行实际标书解析，
   **Then** 使用 doc_chunk 工作区适配路径，任务记录所用策略标识。
3. **Given** doc_chunk 处理失败，**When** 任务结束，
   **Then** 任务标记失败并保留可读错误信息，不破坏 File Import 记录。

---

### Edge Cases

- `.docm` 文件：在调用 doc_chunk 前先转换为 `.docx`（与现有一致），转换失败则任务失败并提示。
- 超大标书（数百 MB、数千节点）：解析应在合理时间内完成或持续汇报进度；不得因节点数异常误报成功。
- 仅含封面图、无正文的目录节点：目录条目存在；候选正文可为空或仅含图片，与既有「仅标题」摘录规则一致。
- 强制重新解析：已确认 Bid Outline 锁定时的差异流程不变。
- doc_chunk 工作区临时目录：解析结束后清理或按策略保留供排障，不得无限堆积占满磁盘。
- Preface 等非目录分块：不得误生成与投标目录无关的候选条目（或标记为可过滤类型）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 对 `file_purpose = actual_bid` 的 Word 解析提供基于 doc_chunk
  的解析路径，消费其工作区产物完成 Document Tree、Bid Outline 与候选知识落库。
- **FR-002**: 系统 MUST 将 doc_chunk 的 `document_tree.json` 映射为 Document Tree 节点，
  节点类型涵盖标题、段落、表格与图片，且节点 ID 在单次导入内唯一、可持久化。
- **FR-003**: 系统 MUST 将 doc_chunk 的 `outline.json` 与 `linkage.json` 映射为 Bid Outline
  及节点与 Document Tree 来源节点的关联（`source_node_id`）。
- **FR-004**: 系统 MUST 以 doc_chunk 章节分块（linkage 主 chunk）生成 Candidate Knowledge，
  正文采用与平台一致的 blocks 结构化格式，图片引用在落库前解析为平台媒体资产 ID。
- **FR-005**: 系统 MUST 在解析任务中汇报与改造前相当粒度的进度阶段，供管理端展示。
- **FR-006**: 系统 MUST 提供配置项在 doc_chunk 路径与 legacy 内置解析路径之间切换，
  默认策略由项目配置明确（见 Assumptions）。
- **FR-007**: 系统 MUST 保留模板标书（`template`）解析的既有实现，不经过本特性适配层。
- **FR-008**: 系统 MUST 保留人工确认门：解析产出仍为 `pending` 候选，未确认内容不得
  进入正式检索或生成输入（Constitution II、III）。
- **FR-009**: 系统 MUST 保留 Bid Outline 人工编辑与结构锁定后的差异同步规则，不得因
  切换解析引擎而静默覆盖已确认目录。
- **FR-010**: 系统 MUST 继续支持章节分类与产品分类的机器建议及人工覆盖；可优先消费
  doc_chunk enrich 元数据作为建议来源，但人工结果仍优先。
- **FR-011**: 系统 MUST 在 doc_chunk 路径失败时明确标记任务失败，不部分写入不可恢复的
  不一致状态（或提供与现有一致的事务/回滚语义）。
- **FR-012**: 系统 MUST 将 `doc_chunk` 作为项目依赖声明并可在部署环境安装，版本与
  `tender_skills` 已验证提交对齐。

### Key Entities

- **Doc Chunk Workspace**: 单次解析在本地或临时存储中的结构化产物集合（正文、目录、
  文档树、分块、图片清单、ID 映射），解析完成后由适配层消费并落库。
- **Parse Strategy**: 标识一次实际标书解析使用 doc_chunk 或 legacy 内置逻辑，
  写入任务元数据供运维与审计。
- **Import Linkage**: outline 节点、文档树 heading 节点与章节分块之间的对应关系，
  用于生成 Bid Outline 来源与候选 `source_node_id`。
- **Document / Document Tree / Bid Outline / Candidate Knowledge**: 与 Epic 3 既有
  定义一致；本特性仅更换生产这些对象的数据来源，不改变其治理语义。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在标准测试标书集（至少包含 1 份无标题样式编号标书、1 份大型多图标书）上，
  doc_chunk 路径解析成功率达到 100%，且投标目录条目数与候选条目数比例处于 `[0.8, 1.2]`
  （排除前言类非目录块）。
- **SC-002**: 确认向导端到端流程（加载任务 → 查看目录与候选 → 提交确认）在 doc_chunk
  路径下可在 5 分钟内由管理员完成，且无阻塞性前端或 API 错误。
- **SC-003**: 抽样不少于 20 条候选知识，正文块渲染（段落、表格、图片）与改造前对照样例
  在视觉与内容上等价，无系统性丢失章节正文。
- **SC-004**: 关闭集成开关后，同一测试标书集的 legacy 解析结果通过既有契约测试基线，
  证明可回退。
- **SC-005**: 模板标书解析回归用例 100% 通过，证明实际标书改造未影响模板路径。
- **SC-006**: 大型标书样例解析端到端耗时不超过改造前基线的 150%，或任务持续输出进度
  直至完成。

## Assumptions

- `tender_skills` 中 doc_chunk 的 002/003 需求已实现并在目标版本通过测试；本仓库以
  固定版本或路径依赖引用该包。
- 首版范围限于实际标书 Word（`.docx`，经 `.docm` 转换）；PDF 实际标书解析不在本特性范围。
- 不移植 doc_chunk 侧的目录 LLM 优化（refine）为默认行为；与现网一致优先规则目录。
- 不强制移植原 `outline_heading_filter`、内嵌附件检测等领域规则；若质量差异可接受，
  由后续 Epic 5 质量特性单独处理。
- 默认启用 doc_chunk 路径可通过配置实现；若未在 Input 中指定，假定 **默认开启 doc_chunk**，
  legacy 仅作回退。
- 临时工作区目录位于应用可写存储下，默认解析成功后删除，失败时保留 24 小时供排障（可配置）。
- 章节分类 UUID 映射仍使用知识库内 Chapter Taxonomy / Product Category 配置；
  doc_chunk 的字符串 hints 仅作机器建议输入。

## Out of Scope

- 模板解析（`template_parse_runner`）改造为 doc_chunk。
- doc_chunk 包内新功能开发（在 `tender_skills` 仓库进行）。
- 检索、生成流水线（Epic 5/6）行为变更。
- 前端确认向导信息架构重做（仅保证兼容现有页面与 API）。
