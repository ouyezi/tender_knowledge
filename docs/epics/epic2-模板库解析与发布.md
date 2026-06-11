# Epic 2：模板库解析与发布

来源：`docs/总需求.md` 的 6.4 至 6.9、7、15.2、17、18 Phase 2、19.1、20、22 相关内容。

## 目标

将单个标书模板文件解析为可治理的模板资产，形成 Template Library、Template、Template Chapter、Template Material，并支持人工编辑与发布。

## 开发定位

这是 V3.0-MVP 的模板链路。模板库在 V3.0 中是知识来源和模块组织建议来源，不是最终标书结构的最高约束。

## 前置依赖

- Epic 0：可选择产品分类和章节分类。
- Epic 1：模板文件已经通过 File Import 导入，并确认 `file_purpose = template_file`。

## 范围

包含：

- Template Library 管理。
- Template 管理。
- Template Chapter 解析和树编辑。
- Template Material 提取和管理。
- Template Variable 基础占位符能力。
- Template Rule 的 MVP 规则。
- 模板文件解析任务。
- 模板发布和版本管理。

不包含：

- 文件夹自动生成 Template Library。
- 复杂变量表达式或脚本计算。
- 完整 Template Instance 生成。
- 招标约束驱动的章节草稿生成。

## 核心对象

### Template Library

表示一组相关标书模板集合。

关键要求：

- 一个模板库可包含多个 Template。
- 模板库不从文件夹自动生成，可由用户在单文件导入时选择或手工创建。
- 模板库发布后才参与模板推荐。
- 模板库保留关联导入文件、作者、更新时间和版本信息。

### Template

表示可实例化的标书结构模板。

关键要求：

- Template 不等同于单个 docx 文件，而是可实例化结构。
- Template 下包含多个 Template Chapter。
- Template 可由模板库解析生成，也可由 Bid Outline 转换生成。

### Template Chapter

表示模板中的章节节点。

关键字段：

- `template_chapter_id`
- `template_id`
- `parent_id`
- `title`
- `level`
- `sort_order`
- `chapter_taxonomy_id`
- `product_category_ids`
- `expected_knowledge_types`
- `bound_wiki_ids`
- `bound_ku_ids`
- `bound_material_ids`
- `variable_ids`
- `rule_ids`
- `required`
- `status`

### Template Material

表示模板章节关联的原始素材文件或片段。

要求：

- Template Material 可作为 KU 或 Wiki 的候选来源。
- PPT、封面、攻略、Excel 类材料在 MVP 只要求保留元数据、附件和适用分类。
- 是否参与语义生成属于后续增强。

### Template Variable

MVP 只支持简单占位符替换，例如 `{{project_name}}`。

要求：

- 变量可设置默认值。
- 变量可要求必填。
- 变量替换结果必须记录在后续生成快照中。

### Template Rule

MVP 只要求支持：

- `required`
- `optional`
- `product_match`

`conditional`、`mutex`、`asset_required` 可在增强阶段实现。

## 主流程

```text
上传单个模板文件
  → 创建 File Import
  → 自动识别文件用途、产品分类和章节类型
  → 人工确认 file_purpose = template_file
  → 解析模板文件
  → 生成 Template / Template Chapter / Template Material / Candidate Knowledge
  → 人工编辑模板结构和素材
  → 发布 Template Library / Template
```

## 模板文件识别规则

- 文件用途确认为 `template_file` 后，进入模板文件解析。
- 文件名包含产品名时，建议 Product Category。
- 文件名或标题包含章节名时，建议 Chapter Taxonomy。
- 文档内标题结构生成 Template Chapter。
- 文档内固定段落、表格、图片生成 Template Material 或 Candidate Knowledge。
- 前缀数字用于章节排序。
- 文件扩展名用于解析策略选择。

## 人工确认项

模板文件解析结果必须进入人工确认界面。

确认项：

- Template Library 归类。
- 产品分类。
- Template Chapter 层级。
- 章节类型。
- 是否作为固定模板章节。
- 是否提取为 KU 或 Wiki。
- 是否忽略。

## 管理后台

模板库中心需要支持：

- Template Library 列表。
- Template 管理。
- Template Chapter 树编辑。
- Template Material 管理。
- 模板变量与规则配置。
- 模板发布和版本管理。

## API

至少需要：

- Template Library 查询。
- Template 查询。
- Template Chapter 查询。
- Template Chapter 更新。
- 模板发布。
- 模板解析任务状态查询。

## 验收标准

1. 用户可以将一个标书模板文件解析为 Template、Template Chapter 和 Template Material。
2. 文档标题结构和编号顺序能转化为 Template Chapter 树。
3. 用户可以编辑章节层级、章节类型、产品分类和排序。
4. 用户可以将模板归类到已有 Template Library，或创建“未归类模板”。
5. 用户可以发布模板库，发布后才参与后续模板推荐。
6. 模板文件解析失败不影响原 File Import 记录，可重新处理。

## 后续依赖

- Epic 4 接收模板解析过程中产生的 Candidate Knowledge。
- Epic 5 检索 Template Chapter 和 Template Material 作为模块建议来源。
- Epic 6 使用 Template Chapter、变量和规则参与生成辅助。
