# Epic 4：候选知识确认工作台

来源：`docs/总需求.md` 的 6.15、8.4、12、15.5、16.3、17、18 Phase 3 后半、19.2、20、22 相关内容。

## 目标

建立候选知识从“待确认”到“正式知识资产”的人工确认工作台，防止未经确认的历史内容污染正式知识库。

## 开发定位

这是 V3.0-MVP 的治理闭环。Epic 3 负责生成候选，本 epic 负责人工确认、编辑、合并、拆分、忽略和发布。

## 前置依赖

- Epic 0：分类底座可用。
- Epic 2 或 Epic 3：已经产生 Candidate Knowledge。

## 范围

包含：

- Candidate Knowledge 列表。
- 按导入批次、产品分类、章节类型、候选类型筛选。
- 候选详情查看。
- 候选标题、摘要、内容编辑。
- 候选合并、拆分、忽略。
- 发布为 KU、Wiki、Template Chapter、Manual Asset、Chapter Pattern、Product Category。
- 批量确认和批量驳回。
- 发布后来源链保留。
- 候选确认 API。

不包含：

- 实际标书解析。
- 模板解析。
- 正式检索策略优化。
- 双人审核和复杂权限流。

## 核心对象

### Candidate Knowledge

关键字段：

- `candidate_id`
- `kb_id`
- `import_id`
- `source_doc_id`
- `source_node_id`
- `candidate_type`
- `title`
- `content`
- `summary`
- `suggested_knowledge_type`
- `suggested_chapter_taxonomy_id`
- `suggested_product_category_ids`
- `confidence_score`
- `status`
- `confirmed_object_type`
- `confirmed_object_id`
- `created_time`
- `updated_time`

`candidate_type` 支持：

- `ku`
- `wiki`
- `template_chapter`
- `manual_asset`
- `chapter_pattern`
- `product_category`
- `ignore`

## 候选区规则

- Candidate Knowledge 默认不参与正式检索。
- 候选区对象不参与普通检索和生成，仅供编辑、审核和确认。
- 人工确认后才发布为 KU、Wiki、Template Chapter、Manual Asset 或 Chapter Pattern。
- Candidate Template Chapter、Candidate Product Category 不单独建表，统一由 Candidate Knowledge 通过 `candidate_type` 表达。
- 发布后必须保留 `candidate_id` 作为来源。

## 发布规则

候选对象发布到正式区时：

- Candidate KU → Knowledge Unit。
- Candidate Wiki → Wiki。
- Candidate Template Chapter → Template Chapter。
- Candidate Manual Asset → Manual Asset。
- Candidate Chapter Pattern → Chapter Pattern。
- Candidate Product Category → Product Category。

发布前必须确认：

- 入库对象类型。
- 标题和摘要。
- 产品分类。
- 章节类型。
- 知识类型。
- 推荐使用方式。
- 是否可检索。
- 来源链是否正确。

## 版本与废弃规则

以下对象需要版本管理：

- KU。
- Wiki。
- Template Library。
- Template。
- Template Chapter。
- Chapter Pattern。

已发布对象不得物理删除，只能废弃。Bid Outline 可保留历史版本，但 MVP 可先记录操作日志。

## 管理后台

候选知识中心需要支持：

- Candidate Knowledge 列表。
- 按批次、产品分类、章节类型筛选。
- 候选合并、拆分、忽略。
- 发布为 KU、Wiki、Template、Manual Asset。
- 批量确认和批量驳回。
- 操作日志查看。

## API

候选知识确认 API 请求：

```json
{
  "candidate_id": "",
  "confirm_as": "ku | wiki | template_chapter | manual_asset | chapter_pattern | product_category | ignore",
  "product_category_ids": [],
  "chapter_taxonomy_id": "",
  "knowledge_type": "",
  "review_comment": ""
}
```

响应：

```json
{
  "candidate_id": "",
  "confirmed_object_type": "",
  "confirmed_object_id": "",
  "status": "published",
  "trace_id": ""
}
```

## 验收标准

1. 用户可以查看按导入批次生成的候选知识列表。
2. 用户可以按产品分类、章节类型、候选类型、状态筛选候选知识。
3. 用户可以编辑候选标题、摘要、内容和分类。
4. 用户可以将候选知识发布为正式 KU、Wiki、Template Chapter、Manual Asset、Chapter Pattern 或 Product Category。
5. 用户可以合并、拆分、忽略候选知识。
6. 批量确认和批量驳回需要记录审计日志。
7. Candidate Knowledge 发布失败可重试。
8. 未确认候选知识不得通过 API 或检索泄露。

## 后续依赖

- Epic 5 只检索已确认、已发布对象。
- Epic 6 只使用已发布知识和用户明确选择的候选内容。
