# Design: 目录蓝图字段精简与生成超时优化

**Date**: 2026-06-22  
**Status**: Approved  
**Related**: `docs/superpowers/specs/2026-06-22-directory-blueprint-generation-extraction-design.md`

---

## 1. 问题

蓝图生成在 60s 内频繁超时。根因是 **输出 token 体量**（子树节点数 × 每节点多字段 JSON），而非输入 prompt 过大。模型 90k 上下文窗口与 HTTP 超时无关。

## 2. 目标

- 一次调用生成完整蓝图（不分批）
- 超时提升至 **120s**
- 从 DB / API / 前端 / LLM Prompt **彻底移除**低价值字段
- Prompt 使用短 key，映射层还原为 API 字段

## 3. 移除字段

### 蓝图级（`knowledge_blueprints`）

| 字段 | 原因 |
|------|------|
| `overall_strategy` | 与 `description` 重叠 |
| `usual_page_range` | 对目录生成技能价值低 |
| `related_regulations` | 常变长，非核心 |
| `common_mistakes` | 培训向，非核心 |
| `template_style` | 与模板元数据重叠 |

### 节点级（`knowledge_blueprint_nodes`）

| 字段 | 原因 |
|------|------|
| `purpose` | 与 `content_description` 重叠 |
| `writing_goal` | 同上 |
| `writing_hint` | 同上 |
| `keyword_hint` | 每节点累加 token，价值有限 |
| `content_type` | 生成价值低 |

## 4. 保留字段

**蓝图**：`name`、`description`、`suggested_structure_md`、标签类、`source_*`、版本状态  
**节点**：`node_title`、`node_level`、`node_order`、`importance_level`、`content_description`、`tender_response_hint`

## 5. LLM 契约（短 key）

```json
{
  "title": "大纲标题",
  "desc": "模块概要",
  "structure_md": "建议目录 Markdown",
  "nodes": [
    { "t": "章节名", "imp": "required", "cd": "内容要点", "tr": "应标线索", "children": [] }
  ]
}
```

映射层同时兼容长 key（测试与旧 mock）。

## 6. 配置变更

| 配置项 | 旧默认 | 新默认 |
|--------|--------|--------|
| `BLUEPRINT_GENERATE_TIMEOUT_SEC` | 60 | **120** |
| `BLUEPRINT_GENERATE_MAX_TOKENS` | 65536 | **16384** |
| `_estimate_max_tokens` per_node | 380 | **220** |

## 7. 迁移

Alembic `20260622_1100_trim_blueprint_fields`：DROP 上述 10 列。

## 8. 预期效果（31 节点示例）

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 估算 max_tokens | 12292 | ~7204 |
| 超时 | 60s | 120s |
| 每节点 LLM 字段数 | ~10 | 4 |
