# Epic 6：生成辅助升级

来源：`docs/总需求.md` 的 6.16、6.17、11、16.2、17、18 Phase 6、19.4、19.5、20、22 相关内容。

## 目标

将 V2.0 的章节生成辅助升级为以外部招标约束为最高优先级、以模块组织建议和知识包为输入的章节草稿辅助能力。

## 开发定位

这是 V3.0-高级阶段能力。它不替代投标人员决策，不自动决定最终标书结构，而是在用户确认外部招标约束和推荐模块后，辅助生成可追溯的章节草稿。

## 前置依赖

- Epic 0：分类底座可用。
- Epic 2：Template Chapter、Template Variable、Template Rule 可用。
- Epic 4：正式 KU、Wiki、Template Chapter、Manual Asset 已发布。
- Epic 5：Module Assembly Suggestion 和 Knowledge Pack 可用。

## 范围

包含：

- Tender Requirement Context 外部招标约束输入。
- Module Assembly Suggestion 创建和消费。
- Template Chapter 变量配置。
- 条件章节规则。
- 生成辅助输入升级。
- 章节草稿生成。
- Generation Snapshot。
- 生成输出引用和冲突提示。

不包含：

- 完整招标文件解析系统。
- 评分规则管理系统。
- 废标项判定系统。
- Word 多人实时协同编辑。
- 标书最终排版和 PDF 交付。
- 自动替用户完成所有章节取舍。

## 核心对象

### Tender Requirement Context

外部招标约束输入，不属于知识库内部资产模型，但在服务层调用时作为最高优先级输入。

至少包含：

- 标书结构要求。
- 章节标题和层级。
- 每个章节的评分点。
- 废标项。
- 格式要求。
- 资质或证明材料要求。
- 响应条款。

### Module Assembly Suggestion

系统基于 Tender Requirement Context 和知识库内容给出的章节模块组织建议。

定位：

- 不是标书模板实例。
- 不决定最终章节结构。
- 只为某个招标文件要求下的目标章节提供历史模块、知识和素材组织建议。
- 最终是否采用由人工根据招标文件要求确认。

关键字段：

- `suggestion_id`
- `kb_id`
- `requirement_context_id`
- `target_outline_node`
- `product_category_ids`
- `suggested_template_chapter_ids`
- `suggested_ku_ids`
- `suggested_wiki_ids`
- `suggested_material_ids`
- `reason`
- `risk_flags`
- `status`
- `created_by`
- `created_time`

### Template Instance

高级预留能力，不作为 MVP 和增强阶段主线能力。

适用场景：

- 用户明确希望按某个历史模板组织完整章节树。
- 需要记录选择了哪些章节。
- 需要记录变量填充值。
- 需要记录每个章节推荐和生成结果。

## Module Assembly Suggestion 创建

输入：

- Tender Requirement Context。
- 产品分类。
- 项目类型。
- 客户类型。
- 目标章节。
- 过滤条件。

输出：

- 推荐 KU、Wiki、素材。
- 推荐历史章节模块。
- 推荐章节组织顺序。
- 与评分点的对应关系。
- 与废标项的风险提示。
- 来源追溯。

## 模板变量

Template Chapter 支持变量。

示例：

- 项目名称。
- 客户名称。
- 产品名称。
- 服务区域。
- 商户数量。
- 交付周期。
- 联系方式。

要求：

- 变量可设置默认值。
- 变量可要求必填。
- MVP 只支持简单占位符，不支持复杂表达式。
- 变量替换必须记录在生成快照中。

## 条件章节

章节可按条件启用：

- 产品分类匹配。
- 客户类型匹配。
- 招标要求包含关键词。
- 必需资质存在。
- 用户手工选择。

规则要求：

- 条件章节只能作为建议，不得覆盖外部招标约束。
- 当模板章节与评分点或废标项冲突时，必须提示风险。
- 用户人工选择优先于模板默认启用结果。

## 生成辅助输入

V3.0 章节草稿生成输入不再只有知识包，也不以模板为主输入，而是包括：

- Tender Requirement Context。
- Module Assembly Suggestion。
- Template Chapter 规则。
- Product Category。
- Bid Outline Node。
- KU/Wiki Knowledge Pack。
- Manual Asset 合规校验结果。
- 变量值。

优先级：

```text
废标项 > 评分点 > 标书结构要求 > 用户人工选择 > 知识包 > 模板库模块建议
```

## 生成输出

输出：

- 章节草稿。
- 每段引用来源。
- 使用的外部招标约束。
- 使用的模板库参考模块。
- 使用的变量。
- 冲突提示。
- 缺失素材提示。
- Generation Snapshot。

Generation Snapshot 至少需要记录：

- `requirement_context_id`
- `suggestion_id`
- `target_outline_node`
- 使用的 KU、Wiki、Template Chapter、Template Material。
- 变量输入和值。
- 检索 trace。
- 生成 prompt 版本。
- 生成结果版本。

## API

复用 Epic 5 的模块组织建议 API，并在生成侧增加：

- 创建章节草稿。
- 查询生成任务状态。
- 查询 Generation Snapshot。
- 重新生成章节草稿。
- 接受或废弃生成结果。

## 验收标准

1. 用户可基于外部招标约束创建 Module Assembly Suggestion。
2. 系统能按评分点、废标项、产品分类推荐章节模块和知识素材。
3. 用户可以查看每条建议的推荐理由、风险提示和来源追溯。
4. 用户可以为 Template Chapter 变量填写值或采用默认值。
5. 生成章节草稿时，废标项和评分点优先于模板库模块建议。
6. 草稿每段内容都能追溯到 Tender Requirement Context、Template Chapter、KU、Wiki 或变量值。
7. 当模板章节与招标要求冲突时，系统提示风险，不自动采用。
8. 生成结果记录 Generation Snapshot，可用于审计和复现。

## 后续扩展

- Template Instance 完整配置和生成。
- 更复杂的条件章节规则。
- 多章节联动生成。
- 与真实投标项目结果关联的模板效果分析。
