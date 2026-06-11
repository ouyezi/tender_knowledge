# Epic 0：分类底座

来源：`docs/总需求.md` 的 4、9、12.4、15.3、20、22 相关内容。

## 目标

先建立产品分类与章节分类两套基础字典，使后续导入、解析、候选知识、检索推荐和生成辅助都有统一的分类口径。

## 开发定位

这是 V3.0 的前置底座，不直接完成文件导入或知识入库，但必须在 Epic 1 之前可用。后续所有对象都应能引用 `Product Category` 和 `Chapter Taxonomy`。

## 范围

包含：

- Product Category 产品分类管理。
- Chapter Taxonomy 章节分类管理。
- 分类同义词、别名、层级关系。
- 分类状态管理：启用、停用、归档。
- 分类影响分析。
- 分类建议结果的人工覆盖机制。

不包含：

- 从文件内容自动训练分类模型。
- 目录级检索推荐。
- 候选知识确认工作台。
- 用户角色和权限体系。

## 核心对象

### Product Category

用于表达产品线、业务线或标书适用产品。

关键字段：

- `category_id`
- `kb_id`
- `parent_id`
- `category_name`
- `category_code`
- `aliases`
- `description`
- `status`
- `created_time`
- `updated_time`

要求：

- 支持多级分类。
- 支持同义词和别名。
- 支持分类合并、停用、归档。
- KU、Wiki、Template、Template Chapter、Bid Outline、Manual Asset 均可关联产品分类。
- 检索、推荐、模块组织建议、生成辅助均支持按产品分类过滤。

### Chapter Taxonomy

用于归一化不同标书中的章节命名。

要求：

- 支持章节类型标准名。
- 支持同义章节名。
- 支持章节层级关系。
- 支持与 Product Category 绑定。
- 支持从 Bid Outline 和 Template Chapter 中自动发现候选章节类型。

## 业务规则

- 模块组织建议优先使用 Product Category 和 Chapter Taxonomy。
- 内容检索优先使用 `knowledge_type`、Product Category 和 Chapter Taxonomy。
- 合规素材推荐优先使用 Manual Asset 类型、Product Category 和有效期。
- `industry`、`project_type`、`customer_type` 作为二级过滤条件。
- 所有分类建议均可由人工覆盖，人工结果优先于自动识别结果。

## 管理后台

产品分类中心需要支持：

- 产品分类树管理。
- 同义词管理。
- 分类合并和停用。
- 分类影响分析。

目录中心在本 epic 中只需要支持 Chapter Taxonomy 的基础维护能力；Bid Outline、Chapter Pattern 的业务使用放到后续 epic。

## API

至少需要提供 Product Category 查询与管理能力：

- 查询分类树。
- 查询分类详情。
- 创建、更新、停用分类。
- 维护别名和同义词。
- 查询分类影响范围。

Chapter Taxonomy 需要提供同等基础能力。

## 验收标准

1. 用户可以创建多级产品分类，并维护别名。
2. 用户可以创建章节分类，并维护同义章节名。
3. 用户可以将章节分类绑定到一个或多个产品分类。
4. 停用或合并分类前，系统可以展示关联 KU、模板、目录和候选知识数量。
5. 后续导入确认页面可以读取并选择这些分类。

## 后续依赖

- Epic 1 使用分类底座做文件用途、产品分类和章节类型确认。
- Epic 2 使用分类底座标记 Template、Template Chapter、Template Material。
- Epic 3 使用分类底座标记 Bid Outline、Bid Outline Node 和候选知识。
- Epic 5 使用分类底座做目录级检索和模块建议过滤。
