# Epic 5：目录级检索与模块建议

来源：`docs/总需求.md` 的 6.16、10、13、15.4、15.7、16.2、17、18 Phase 4 和 Phase 5、19.3、19.4、19.6、20、22 相关内容。

## 目标

基于外部招标约束、目标目录、产品分类和已发布知识资产，提供目录级检索、历史模块推荐、缺失章节诊断和检索准确率优化闭环。

## 开发定位

这是 V3.0-增强阶段能力。它不负责生成章节草稿，只负责“找结构、找模块、找知识、解释为什么推荐、收集反馈优化检索”。

## 前置依赖

- Epic 0：分类底座可用。
- Epic 2：Template Chapter、Template Material 已发布。
- Epic 3：Bid Outline、Bid Outline Node、Chapter Pattern 已生成。
- Epic 4：候选知识已确认发布。

## 范围

包含：

- Bid Outline 检索。
- Bid Outline Node 检索。
- Template Chapter 检索。
- Chapter Pattern 检索。
- 目录匹配评分。
- 模块组织建议。
- 章节缺失诊断。
- Module Assembly Suggestion 初版。
- 检索请求参数模型。
- `retrieval_trace`。
- 检索反馈采集。
- 检索评测集。
- 检索策略版本管理。

不包含：

- 章节草稿生成。
- Template Instance 完整实例化。
- 复杂自动学习系统。
- 招标文件完整解析系统。

## 检索对象

新增或增强的检索对象：

- KU：语义 + 关键词 + 元数据，用于内容知识检索。
- Wiki：语义 + 关键词 + 元数据，用于标准内容检索。
- Template：元数据 + 结构匹配，用于模板推荐。
- Template Chapter：语义 + 章节匹配，用于章节模板推荐。
- Bid Outline：结构匹配，用于历史目录匹配。
- Chapter Pattern：结构匹配，用于常见章节推荐。
- Manual Asset：元数据过滤，用于合规素材推荐。

## 目录匹配流程

```text
输入外部招标约束中的目标目录 / 章节标题 / 评分点
  → 章节标题标准化
  → 匹配 Chapter Taxonomy
  → 检索历史 Bid Outline
  → 检索 Template Chapter
  → 检索 Chapter Pattern
  → 返回相似目录、候选模块和组织建议
```

## 匹配评分

增强阶段先采用可解释规则评分。

`match_score` 默认权重：

- 产品分类匹配：30%。
- 章节分类覆盖：30%。
- 标题语义相似：20%。
- 层级顺序相似：10%。
- 可用知识覆盖：10%。

`coverage_rate`：

```text
coverage_rate = 已匹配目标章节数 / 目标章节总数
```

缺失章节判断：

- 目标目录缺少该产品分类下高频 Chapter Pattern。
- 默认阈值：同一产品分类下出现频次大于等于 3 次，或出现比例大于等于 30%。

## 模块组织建议

输入：

- 产品分类。
- 项目类型。
- 客户类型。
- 外部招标文件结构要求。
- 评分点。
- 废标项。
- 目标章节要求。

输出：

- 推荐 Template Chapter 或历史章节模块。
- 推荐 KU、Wiki、素材。
- 推荐组织顺序和组合方式。
- 与招标文件要求的覆盖度。
- 缺失章节提示。
- 可用 KU、Wiki 数量。
- 风险提示。
- 推荐理由和来源追溯。

原则：

- 招标文件中的结构要求、评分点和废标项优先于模板库建议。
- 模板库只提供历史写法和小模块组织参考。
- 若模板章节与招标要求冲突，必须提示风险，不得自动采用模板章节。

## 检索请求参数模型

检索请求不应只有 query 文本，还应包含业务上下文、召回配置、排序配置和返回配置。

建议参数：

```json
{
  "query": "",
  "intent": "knowledge_lookup | material_recommend | module_suggestion | trace_lookup",
  "product_category_ids": [],
  "chapter_taxonomy_ids": [],
  "knowledge_types": [],
  "file_purposes": [],
  "tender_requirement_context": {
    "outline_title": "",
    "score_points": [],
    "rejection_clauses": []
  },
  "retrieval_options": {
    "enable_bm25": true,
    "enable_vector": true,
    "enable_rerank": true,
    "top_k": 20,
    "context_expand_depth": 1
  },
  "return_options": {
    "include_trace": true,
    "include_score_detail": true,
    "include_conflict_flags": true
  }
}
```

要求：

- 不同 intent 可使用不同召回策略和排序策略。
- 检索参数必须记录到 `retrieval_trace`。
- 返回结果必须包含 score、score_detail、命中原因和来源追溯。
- 前端或调用方可调整 top_k、过滤条件、是否启用上下文扩展。

## Knowledge Pack 升级

Knowledge Pack 新增：

- `product_category`
- `chapter_taxonomy`
- `template_chapter_hints`
- `bid_outline_context`
- `chapter_patterns`
- `candidate_source`
- `import_id`
- `score_detail`
- `hit_reason`

## 检索反馈与评测闭环

反馈数据：

- 点击。
- 采纳。
- 复制。
- 加入草稿。
- 用户标记“有用/无用”。
- 用户标记“误召回”。
- 用户标记“漏召回”，并可补充期望结果。
- 人工调整产品分类、章节类型、知识类型。

评测指标：

- Recall@K。
- Precision@K。
- MRR。
- NDCG。
- 采纳率。
- 误召回率。
- 漏召回率。
- 有来源结果占比。

要求：

- 检索策略、Prompt、Embedding、Rerank 配置均需要版本号。
- 每次检索优化前后应能在同一评测集上对比指标。
- 线上反馈可转为评测用例，但必须人工确认后进入正式评测集。

## 管理后台

目录中心需要支持：

- Bid Outline 列表。
- Bid Outline 节点编辑。
- Chapter Taxonomy 映射。
- Chapter Pattern 确认。
- 目录相似度查看。

检索优化中心需要支持：

- 查看检索请求日志和 `retrieval_trace`。
- 查看查询参数、过滤条件、召回结果和排序结果。
- 收集点击、采纳、无用、误召回、漏召回反馈。
- 管理检索评测集。
- 对比不同检索策略版本指标。
- 管理 BM25 权重、向量召回、Rerank、上下文扩展等策略配置。

## API

模块组织建议 API 请求：

```json
{
  "kb_id": "",
  "tender_requirement_context": {
    "outline_nodes": [],
    "score_points": [],
    "rejection_clauses": [],
    "format_requirements": []
  },
  "product_category_ids": [],
  "project_type": "",
  "customer_type": "",
  "outline_nodes": [
    {
      "title": "",
      "level": 1
    }
  ],
  "requirement_text": ""
}
```

响应：

```json
{
  "module_suggestions": [
    {
      "suggestion_id": "",
      "target_outline_node": {},
      "suggested_template_chapter_ids": [],
      "suggested_ku_ids": [],
      "suggested_wiki_ids": [],
      "match_score": 0.0,
      "coverage_rate": 0.0,
      "score_point_coverage": [],
      "rejection_risks": [],
      "risk_flags": []
    }
  ],
  "trace_id": ""
}
```

同时需要 Retrieval Feedback API 和 Retrieval Eval API。

## 验收标准

1. 用户选择产品分类和目标章节后，系统优先推荐相关 KU、Template Chapter 和 Chapter Pattern。
2. 系统会过滤不适用产品分类的素材。
3. 输入外部招标约束、目标目录和产品分类后，系统能推荐相关历史模块、知识和素材。
4. 返回结果包含评分点覆盖情况、废标风险、缺失素材和推荐理由。
5. 目录匹配结果能展示 `match_score`、`coverage_rate` 和 `score_detail`。
6. 每次检索可记录 query、intent、过滤条件、召回策略、排序策略和返回结果。
7. 用户可提交有用、无用、误召回、漏召回反馈。
8. 同一评测集可对比不同检索策略版本的指标变化。

## 后续依赖

- Epic 6 消费 Module Assembly Suggestion 和 Knowledge Pack 生成章节草稿。
