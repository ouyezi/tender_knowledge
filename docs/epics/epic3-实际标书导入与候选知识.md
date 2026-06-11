# Epic 3：实际标书导入与候选知识

来源：`docs/总需求.md` 的 6.1 至 6.3、6.10 至 6.15、8.1 至 8.3、15.4、17、18 Phase 3 前半、19.2、20、22 相关内容。

## 目标

将实际标书文件解析为文档结构、可编辑目录和候选知识，为后续人工确认入库提供原始候选资产。

## 开发定位

这是 V3.0-MVP 的实际标书解析链路前半段。它负责“解析与生成候选”，不负责候选知识最终确认、发布和治理。

## 前置依赖

- Epic 0：可选择产品分类和章节分类。
- Epic 1：实际标书已经通过 File Import 导入，并确认 `file_purpose = actual_bid`。

## 范围

包含：

- Document 来源字段扩展。
- Document Tree Node 目录相关字段扩展。
- Bid Outline 生成。
- Bid Outline Node 生成和编辑。
- Document Tree 与 Bid Outline 关联。
- Chapter Pattern 候选生成。
- Candidate Knowledge 生成。
- 实际标书解析任务。

不包含：

- Candidate Knowledge 确认和发布。
- 候选知识合并、拆分、批量确认。
- 目录级检索和模板推荐。
- 招标文件评分点、废标项解析。

## 核心对象

### Document

V3.0 新增来源字段：

- `import_id`
- `source_type`
- `source_usage`
- `product_category_ids`
- `bid_project_name`
- `bid_customer_name`

要求：

- 实际标书导入时 `source_type = actual_bid`。
- Document 解析后可同时产生 Document Tree、Bid Outline 和 Candidate Knowledge。

### Document Tree Node

新增与目录沉淀相关字段：

- `chapter_taxonomy_id`
- `product_category_ids`
- `is_outline_node`
- `candidate_template_chapter_id`
- `candidate_pattern_id`

要求：

- 实际标书中的章节节点可被映射到 Chapter Taxonomy。
- 高价值章节节点可生成 Candidate Knowledge。
- 目录节点可生成 Bid Outline Node。

### Bid Outline

表示实际标书或目标标书的目录结构。

要求：

- 实际标书导入后自动生成 Bid Outline。
- 用户可编辑、合并、删除目录节点。
- 确认后的 Bid Outline 可参与目录检索和模块组织建议。

### Bid Outline Node

表示 Bid Outline 中的单个目录节点。

关键字段：

- `outline_node_id`
- `bid_outline_id`
- `parent_id`
- `title`
- `level`
- `sort_order`
- `chapter_taxonomy_id`
- `source_node_id`
- `product_category_ids`
- `status`

### Chapter Pattern

从多个 Bid Outline 和 Template Chapter 中归纳出的章节模式。

本 epic 只需要生成候选 Chapter Pattern；确认和正式治理放到 Epic 4。

### Candidate Knowledge

表示从文档、模板、实际标书、PPT、资质材料中提取但尚未确认的候选知识。

本 epic 只负责创建 `pending` 状态候选，确认、合并、拆分、发布放到 Epic 4。

## 主流程

```text
上传实际标书
  → File Import 确认为 actual_bid
  → Document 解析
  → Document Tree 生成
  → Bid Outline 抽取
  → Candidate Knowledge 生成
  → 进入候选确认工作台
```

## Bid Outline 抽取规则

- 优先使用文档内置目录。
- 其次使用标题样式和编号规则。
- 支持人工修正目录。
- 支持将目录节点映射到 Chapter Taxonomy。
- 用户编辑 Bid Outline 不自动修改 Document Tree。
- 用户编辑 Document Tree 不自动覆盖已确认 Bid Outline。
- 文档重新解析后，只生成 Bid Outline 差异建议，由人工选择是否同步。

## Candidate Knowledge 生成规则

- 技术方案章节生成方案类 KU 候选。
- 产品功能章节生成产品或能力说明类 KU 候选。
- 供应链章节生成能力说明或方案类 KU 候选。
- 企业实力、资质、荣誉章节生成资质或能力类 KU 候选。
- 稳定通用段落可推荐为 Wiki 候选。
- 候选知识必须保留来源链：File Import、Document、Document Tree Node。

## 管理后台

目录中心在本 epic 中需要支持：

- Bid Outline 列表。
- Bid Outline 节点编辑。
- Chapter Taxonomy 映射。
- 目录抽取任务日志查看。

候选知识中心在本 epic 中只需要能查看由解析产生的候选列表，确认能力放到 Epic 4。

## 任务中心

本 epic 需要的任务类型：

- `bid_outline_extract`
- `candidate_knowledge_generate`
- `chapter_pattern_mining`

## 验收标准

1. 实际标书导入后可生成 Document 和 Document Tree。
2. 系统可以从实际标书抽取可编辑 Bid Outline。
3. 用户可以确认目录节点的章节类型和产品分类。
4. 系统可以从实际标书章节生成候选 KU、Wiki、Chapter Pattern。
5. Candidate Knowledge 默认不参与正式检索。
6. 每个候选知识都能追溯到 File Import、Document 和来源节点。

## 后续依赖

- Epic 4 负责候选知识确认、发布和治理。
- Epic 5 使用 Bid Outline、Bid Outline Node、Chapter Pattern 做目录级检索。
