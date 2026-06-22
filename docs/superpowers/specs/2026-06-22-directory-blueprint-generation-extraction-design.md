# Design: 目录蓝图 — 目录生成能力提取（V1.1）

**Date**: 2026-06-22  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-21-directory-blueprint-design.md` · Epic 5 模块建议 · Epic 6 Tender Requirement Context（后续合并）  
**Problem**: 目录蓝图 V1 仅从标题层级提取写作指导，缺少「内容描述」「应标/得分/应答线索」及「建议目录结构」模块，无法作为后续目录生成技能与多源蓝图合并的基础。

---

## 1. 背景与目标

### 1.1 痛点

| 痛点 | 说明 |
|------|------|
| 生成输入单薄 | V1 仅传标题层级，LLM 难以推断章节实际写什么 |
| 缺少应答视角 | 无法从历史章节沉淀「可能应标/得分/应答」关注点 |
| 结构建议缺失 | 源目录树镜像历史文档，缺少逻辑模块层面的组织建议 |
| 技能基础不足 | 后续目录生成技能、与模板/招标约束合并时缺少结构化锚点 |

### 1.2 产品定位

在目录蓝图 V1 上增量增强「目录生成能力提取」：以**历史标书/模板章节目录**为主输入，结合子树 `content_preview` 聚合摘要，一次性生成可编辑、可沉淀的四类能力字段，为后续目录生成技能与多源蓝图合并提供基础。

### 1.3 建设目标

从历史文档目录子树提取并 AI 归纳：

| 能力 | 字段 | 层级 |
|------|------|------|
| a. 标题 | `node_title`（已有） | 节点 |
| b. 内容描述 | `content_description`（新增） | 节点 |
| c. 应标/得分/应答 | `tender_response_hint`（新增，可空文本） | 节点 |
| d. 建议目录结构 | `suggested_structure_md`（新增，Markdown） | 蓝图 |

### 1.4 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 输入来源 | 历史标书/模板章节目录（非招标约束） |
| 上下文 | 目录层级 + 子树 `content_preview` 聚合摘要（不用全文、不做额外 LLM 摘要） |
| 实现方案 | 方案 A：V1 蓝图增量扩展（单次 generate） |
| b/c 粒度 | 章节节点级 |
| c 存储形态 | 单一文本，应标项/得分点/应答条目遇则写入，不强制分项字段 |
| d 建议结构 | 蓝图级独立模块；Markdown 模块化分组描述，非完全结构化树 |
| 现有写作字段 | 保留 `purpose` / `writing_goal` / `writing_hint`，新增 `content_description` 独立并存 |
| Epic 6 对接 | 本次不做；留作后续与招标约束合并 |

---

## 2. 范围

### 2.1 包含

- `collect_subtree_outline` 增强：为每个 heading 附加 `content_summary`
- LLM Prompt / JSON 解析扩展三字段
- DB 迁移（蓝图 1 列 + 节点 2 列）
- API Schema、Service、前端编辑器 UI 同步
- 单元测试与既有 generate → save 流程兼容

### 2.2 不包含

- 接入 `TenderRequirementContext`（Epic 6）
- 建议目录结构的结构化树或独立表
- 生成阶段 LLM 摘要（`content_preview` 不足时不补调 LLM）
- 与 Template Chapter / Chapter Pattern 的自动合并生成
- 蓝图列表页新增筛选维度

---

## 3. 数据模型

### 3.1 迁移

```sql
ALTER TABLE knowledge_blueprints
  ADD COLUMN suggested_structure_md TEXT NULL;

ALTER TABLE knowledge_blueprint_nodes
  ADD COLUMN content_description TEXT NULL,
  ADD COLUMN tender_response_hint TEXT NULL;
```

旧数据三列均为 `NULL`，向后兼容。已有蓝图可编辑补全或重新生成。

### 3.2 字段说明

#### `knowledge_blueprints.suggested_structure_md`

- 类型：`TEXT NULL`
- 语义：按逻辑模块（如「技术方案」「商务响应」「资质证明」）用 Markdown 分段描述建议目录组织；可引用源章节标题作映射参考
- 最大长度：1500 字（服务层截断）

#### `knowledge_blueprint_nodes.content_description`

- 类型：`TEXT NULL`
- 语义：本章应写什么的内容描述（1–2 句），与 `purpose`/`writing_goal`/`writing_hint` 分工不同
- 最大长度：200 字

#### `knowledge_blueprint_nodes.tender_response_hint`

- 类型：`TEXT NULL`
- 语义：从历史章节推断的「可能」应标关注点；应标项、得分点、应答条目自然语言混写，遇则写、可空
- 最大长度：300 字
- **非**真实招标文件条款

### 3.3 节点字段全景

```text
节点级
├── node_title              # a. 标题（已有）
├── content_description     # b. 内容描述（新）
├── tender_response_hint    # c. 应标相关（新，可空）
├── purpose                 # 编写目的（保留）
├── writing_goal            # 写作目标（保留）
├── writing_hint            # 写作提示（保留）
└── importance_level / content_type / keyword_hint（保留）

蓝图级
├── name / description / overall_strategy / ...（保留）
└── suggested_structure_md  # d. 建议目录结构（新）
```

---

## 4. 生成流程

### 4.1 输入增强

在 `collect_subtree_outline` 输出的每个 heading 节点上附加 `content_summary`：

```text
对每个 heading 节点：
  1. 收集该节点子树下所有 node_type != heading 的子节点 content_preview
  2. 按 sort_order 拼接，去重空白
  3. 截断至 800 字符（复用 truncate_for_llm）
  4. 无 preview 时 content_summary = ""（不阻断生成）
```

输出结构示例：

```json
{
  "node_title": "技术方案",
  "node_level": 2,
  "content_summary": "本章节介绍总体架构与部署方案……",
  "children": []
}
```

### 4.2 LLM Prompt

**System prompt**（在 V1 基础上扩展 JSON 字段要求）：

- 顶层新增：`suggested_structure_md`（Markdown，按逻辑模块分段描述建议目录组织）
- 节点新增：`content_description`（1–2 句）、`tender_response_hint`（可省略；有线索时 1–2 句）
- 保留 V1 全部字段：`outline_title`、`overall_strategy`、`nodes[]` 及写作相关字段

**User prompt**：`目录子树（含 content_summary）：\n{json}`

**生成约束（轻量化）**：

- `content_description`：每节点 ≤ 200 字
- `tender_response_hint`：可空；有则 ≤ 300 字
- `suggested_structure_md`：≤ 1500 字

### 4.3 解析与归一化

- `_normalize_nodes` 解析 `content_description`、`tender_response_hint` 并截断
- `generate_blueprint_draft` 返回体增加 `suggested_structure_md`
- `_wrap_nodes_with_source_root` 根节点同步传递新字段
- `max_tokens` 估算：`per_node` 280 → 380

### 4.4 模块变更

```text
backend/src/services/knowledge/
├── blueprint_generate_service.py   # + aggregate_content_summary()
├── blueprint_service.py            # CRUD 透传新字段
└── blueprint_tree_utils.py         # flatten/nest 自动透传（无变更逻辑）

backend/src/models/
├── knowledge_blueprint.py          # + suggested_structure_md
└── knowledge_blueprint_node.py     # + content_description, tender_response_hint

backend/alembic/versions/YYYYMMDD_blueprint_generation_extraction.py
```

---

## 5. API 契约

**前缀**：`/api/v1/kbs/{kb_id}/blueprints`（无新端点）

### 5.1 Schema 变更

`BlueprintNodeInput` / 节点响应：

```python
content_description: str | None = None
tender_response_hint: str | None = None
```

`SaveBlueprintRequest` / 蓝图详情响应：

```python
suggested_structure_md: str | None = None
```

`POST /blueprints/generate` 响应草稿同步包含上述字段。

### 5.2 校验

| 字段 | 保存时 |
|------|--------|
| `content_description` | 超长截断至 200 字 |
| `tender_response_hint` | 超长截断至 300 字 |
| `suggested_structure_md` | 超长截断至 1500 字 |

截断不阻断保存；服务层记录 warning 日志。

### 5.3 错误码

沿用 V1：`document_not_ready`、`no_child_nodes`、`blueprint_generate_timeout`、`blueprint_generate_failed`。LLM 未返回新字段时存 `null`，不视为失败。

---

## 6. 前端设计

### 6.1 类型扩展

`frontend/src/services/blueprints.ts`：

- `BlueprintNode` 增加 `content_description?`、`tender_response_hint?`
- `BlueprintDraft` 增加 `suggested_structure_md?`

### 6.2 新增组件

`frontend/src/components/Blueprint/BlueprintSuggestedStructure.tsx`

- Markdown 多行文本编辑（`Input.TextArea`）
- 只读模式纯展示
- 可折叠，默认展开

### 6.3 编辑器布局（`BlueprintEditor`）

```text
[来源信息 Alert]
[蓝图元信息 Card — BlueprintMetaForm]
[建议目录结构 Card — BlueprintSuggestedStructure]   ← 新增
[目录大纲 | 节点详情 Row]
[重新生成 | 保存为蓝图]
```

### 6.4 节点详情（`BlueprintNodeDetailPanel`）

新增「生成指导」分组（默认展开）：

| 表单项 | 控件 | 说明 |
|--------|------|------|
| 内容描述 | TextArea 2 行 | `content_description` |
| 应标/得分/应答提示 | TextArea 2 行 | `tender_response_hint`；placeholder 说明「从历史章节推断，遇则填写，可留空」 |

原有「编写目的 / 写作目标 / 写作提示」等归入「写作策略」分组，可折叠。

### 6.5 详情页

`BlueprintDetailPage` 只读展示新字段；空值显示「—」。

---

## 7. 边界与异常

| 场景 | 处理 |
|------|------|
| 节点无 `content_preview` | `content_summary=""`，照常生成 |
| LLM 未返回新字段 | 存 `null` |
| 子树过大 / 超时 | 504 + 重试；摘要 800 字截断控 prompt |
| 重新生成 | Modal 确认后覆盖全部字段（含新字段） |
| 旧蓝图编辑 | 新字段为空，可手动补或重新生成 |
| 文档 purge | 级联删除逻辑不变 |

---

## 8. 测试策略

### 8.1 后端单元

- `aggregate_content_summary`：多段落聚合、截断、空 preview、仅 heading 无正文
- `_normalize_nodes`：新字段解析、超长截断、缺失字段默认 null
- `generate_blueprint_draft`：mock LLM 含新字段的全流程
- `blueprint_service`：保存/读取新字段 round-trip

### 8.2 集成

- generate → create → GET 详情含新字段
- PUT 更新 `suggested_structure_md` 与节点新字段

### 8.3 手工 Smoke

1. 选有正文的章节 → 提取 → 检查三字段有合理初值  
2. 编辑节点「内容描述」「应标提示」→ 保存 → 详情页回显  
3. 编辑「建议目录结构」Markdown → 保存 → 列表进入详情可见  
4. 重新生成 → 确认覆盖新字段  

---

## 9. 后续扩展

| 方向 | 说明 |
|------|------|
| 目录生成技能 | `suggested_structure_md` + 节点 `content_description` 作为技能输入 |
| Epic 6 合并 | `tender_response_hint` 与 `TenderRequirementContext.score_points` / `response_clauses` 对齐映射 |
| 多源蓝图合并 | 与 Template Chapter、Chapter Pattern、招标约束综合生成目录方案 |
| 结构化升级 | 可选将 `suggested_structure_md` 解析为模块树（非本次范围） |

---

## 10. 与 Constitution 对齐

- **Chapter-First**：增强仍以章节节点为边界，摘要来自章节子树
- **Human Confirmation Gate**：generate 产出草稿，保存前可编辑
- **Knowledge Asset First**：蓝图为独立知识资产，与 `knowledge_chunks` 解耦
- **Retrieval Before Generation**：本次为资产沉淀；检索/生成消费留后续 Epic
