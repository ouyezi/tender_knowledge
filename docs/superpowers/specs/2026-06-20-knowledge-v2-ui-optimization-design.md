# Design: 知识录入 V2 / 知识浏览 V2 UI 优化

**Date**: 2026-06-20  
**Status**: Approved  
**Related**: `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md` · `frontend/src/pages/KnowledgeV2/` · `backend/src/services/knowledge_v2/prefill_service.py`

## 1. 背景与目标

### 1.1 现状

知识 V2 录入与浏览页已可用，但面向业务人员的体验不足：

| 页面 | 问题 |
|------|------|
| 知识录入 V2 | 章节预览仅展示 Markdown 源码；图片/表格在独立资产卡片；三栏固定比例；表单字段名为英文 |
| 知识浏览 V2 | 17 个筛选字段全部展开占高；label 为英文字段名；列表列名为英文 |
| 知识详情 Drawer | 正文为纯文本 `<pre>`；字段 label 为英文 |

后端枚举定义在 `prefill_service.py`，前端尚无统一中文映射。项目使用 Ant Design 5.28，支持 `Splitter`；当前无 Markdown 渲染依赖。

### 1.2 目标

1. 章节预览支持 **预览 / 源码** 切换，默认预览；Markdown 与图片/表格资产在同一连续阅读视图中展示。
2. 录入页目录树、章节预览、知识录入三栏 **两处可拖拽** 调宽；顶部文档选择 **单行紧凑**。
3. 录入表单、浏览筛选、列表、详情 **全页面中文化**（字段名 + 枚举值显示）；映射集中到单一字典文件。
4. 浏览筛选默认 **一行 4 字段**，可展开完整筛选。
5. 详情页内容默认 **格式化预览**（与录入预览复用同一组件）。

### 1.3 不在范围

- 后端 API、枚举定义、AI 预填逻辑变更
- 浏览筛选业务逻辑变更（仅布局与中文化）
- 国际化多语言框架
- 录入表单字段增删

---

## 2. 用户决策（Brainstorming 确认）

| 维度 | 决议 |
|------|------|
| 章节预览模式 | **C**：Markdown + 资产内联连续阅读；可切源码 |
| 顶部文档区 | **A**：单行紧凑（标签 + Select），去掉独立 Card |
| 浏览筛选收起 | **B**：默认分类、知识类型、状态、关键词 + 展开按钮 |
| 分栏拖拽 | **B**：目录树↔预览、预览↔录入 两处可拖 |
| 中文范围 | **B**：筛选、列表、录入、详情全中文化；API 仍传英文枚举 |

---

## 3. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 共享组件 + 元数据字典** | `knowledgeChunkMeta.ts` + `KnowledgeContentViewer` + Ant Design `Splitter` + `react-markdown` | 改动集中、体验一致 | 新增 2 个 npm 依赖 |
| ② 各页各自实现 | 三页分别写预览与中文化 | 无新依赖 | 重复代码、难维护 |
| ③ i18n 框架 | `react-i18next` 管理文案 | 可扩展多语言 | 当前仅需中文，过度设计 |

**决议：方案 ①**

---

## 4. 架构与文件结构

```text
frontend/src/
├── constants/
│   └── knowledgeChunkMeta.ts           # 字段中文名、枚举中文、Select options 工厂
├── components/KnowledgeV2/
│   ├── KnowledgeContentViewer.tsx      # 预览/源码切换 + 连续阅读渲染
│   ├── buildContentBlocks.ts           # content_md + assets → 有序块
│   └── ResizableWorkspace.tsx          # 三栏嵌套 Splitter
└── pages/KnowledgeV2/
    ├── KnowledgeEntryPage.tsx          # 改造
    ├── KnowledgeBrowsePage.tsx         # 改造
    └── KnowledgeChunkDetailDrawer.tsx  # 改造
```

**边界**：仅前端变更；`knowledgeChunkMeta.ts` 枚举集合与 `prefill_service.py` 保持对齐，后端为 source of truth。

---

## 5. 统一元数据字典 `knowledgeChunkMeta.ts`

### 5.1 字段中文名（`FIELD_LABELS`）

覆盖录入表单、浏览筛选、列表列名、详情 `Descriptions`：

| 字段 | 中文 |
|------|------|
| title | 标题 |
| content | 内容 |
| summary | 摘要 |
| knowledge_type | 知识类型 |
| content_type | 内容类型 |
| source_type | 来源类型 |
| file_name | 文件名 |
| project_name | 项目名称 |
| category | 分类 |
| status | 状态 |
| quote_mode | 引用模式 |
| template_type | 模板类型 |
| security_level | 安全级别 |
| review_status | 审核状态 |
| owner | 负责人 |
| issue_date | 生效日期 |
| expire_date | 失效日期 |
| tags | 标签 |
| products | 产品 |
| industries | 行业 |
| customer_types | 客户类型 |
| regions | 地区 |
| page_start | 起始页 |
| page_end | 结束页 |
| char_start | 起始字符 |
| char_end | 结束字符 |
| parent_id | 父级 ID |
| retrieval_weight | 检索权重 |
| edit_distance_avg | 平均编辑距离 |
| catalog_path | 目录路径 |
| variables | 变量 |
| exclusion_rules | 排除规则 |
| need_parent_context | 需要父级上下文 |
| is_template | 是否模板 |
| is_immutable | 是否不可变 |
| winning_flag | 中标标记 |
| keyword | 关键词 |
| issue_date_from | 生效日期起 |
| issue_date_to | 生效日期止 |
| expire_date_from | 失效日期起 |
| expire_date_to | 失效日期止 |
| id | ID |
| kb_id | 知识库 ID |
| knowledge_code | 知识编码 |
| version | 版本 |
| previous_version_id | 上一版本 ID |
| is_latest | 是否最新 |
| doc_id | 文档 ID |
| primary_node_id | 主节点 ID |
| token_count | Token 数 |
| content_hash | 内容哈希 |
| has_children | 是否有子节点 |
| children_count | 子节点数 |
| create_time | 创建时间 |
| update_time | 更新时间 |
| embedding_status | 向量状态 |
| previous_version | 上一版本 |
| asset_code | 资产编码 |
| chunk_id | 知识块 ID |
| table_type | 表格类型 |
| image_type | 图片类型 |
| allow_row_filter | 允许行过滤 |
| required_with_text | 与正文绑定 |
| position_hint | 位置提示 |
| image_caption | 图片说明 |
| image_ocr_text | 图片 OCR |
| llm_summary | LLM 摘要 |
| table_summary | 表格摘要 |
| table_schema | 表格结构 |
| table_headers | 表头 |
| table_rows | 表格行 |

### 5.2 枚举值中文（`ENUM_LABELS`）

与 `prefill_service.py` 对齐：

| 字段 | 值 | 中文 |
|------|-----|------|
| knowledge_type | fact / template / solution / case / table / image | 事实 / 模板 / 方案 / 案例 / 表格 / 图片 |
| content_type | text / mixed | 文本 / 混合 |
| source_type | bid / proposal / qualification / contract / manual / wiki / case | 标书 / 投标方案 / 资质 / 合同 / 手册 / 百科 / 案例 |
| category | qualification / technical / business / legal / personnel / price / case / template | 资质 / 技术 / 商务 / 法务 / 人员 / 报价 / 案例 / 模板 |
| status | draft / active / deprecated / disabled | 草稿 / 生效 / 已废弃 / 已禁用 |
| security_level | public / internal / confidential | 公开 / 内部 / 机密 |
| review_status | pending / approved / rejected | 待审核 / 已通过 / 已驳回 |
| quote_mode | full / partial | 全文引用 / 部分引用 |
| template_type | commitment / authorization / response / technical_solution / implementation_plan / service_plan / quotation | 承诺函 / 授权书 / 响应说明 / 技术方案 / 实施方案 / 服务方案 / 报价 |
| embedding_status | pending / ready / failed | 待处理 / 已完成 / 失败 |

文档来源展示：`template` 文档名后缀「（模板）」逻辑保留。

### 5.3 工具函数

```typescript
getFieldLabel(field: string): string
getEnumLabel(field: string, value: string | null | undefined): string
getEnumOptions(field: string): { value: string; label: string }[]
formatBoolean(value: boolean | null | undefined): string  // 是 / 否 / -
```

未知字段或枚举值：回退显示原英文字符串，不阻断渲染。

---

## 6. 共享内容预览 `KnowledgeContentViewer`

### 6.1 预览模式（默认）

1. `buildContentBlocks({ contentMd, assets, sectionCharStart? })`：
   - 将 `assets` 按 `char_start` 升序排列
   - 有 `char_start` 且落在章节范围内的资产，按相对偏移切成「文本段 + 资产段」交替序列
   - 无位置信息的资产追加到末尾
2. 文本段：`react-markdown` + `remark-gfm`
3. 资产段：复用现有 `renderAsset`（图片、Markdown 表格转 HTML、fallback pre）
4. 各段垂直堆叠，形成连续阅读流

### 6.2 源码模式

- 正文：`content_md` 全文 `<pre>`
- 资产：底部折叠面板列出（类型 + ID），展开可看 `raw_markdown`

### 6.3 切换控件

Card `extra` 或标题行右侧：`Segmented` — `预览 | 源码`，默认 `预览`。

### 6.4 复用点

| 位置 | 默认模式 |
|------|----------|
| 录入页「章节预览」 | 预览 |
| 详情页「内容」Card | 预览 |

录入页移除现有独立资产 Card 列表（内联到预览模式）。

---

## 7. 知识录入页改造

### 7.1 顶部文档选择

- 移除 `Card title="选择来源文档"`
- 改为单行：`来源文档：` + `Select`（`flex` 横向，`alignItems: center`）
- 选项 label 逻辑不变（模板文档加「（模板）」后缀）

### 7.2 三栏可拖拽布局 `ResizableWorkspace`

- 外层 `Splitter`：目录树 | 右区
- 内层 `Splitter`（右区）：章节预览 | 知识录入
- 默认比例约 **20% / 45% / 35%**
- 每 pane `min` 约 200px
- `onResizeEnd` 将比例写入 `localStorage`（key: `knowledge-v2-entry-layout`）
- 读取失败或无效时回退默认比例

### 7.3 章节预览 Card

- 标题行：`章节预览` + `Segmented` 模式切换 + `添加到知识库` 按钮
- 内容区：`KnowledgeContentViewer`

### 7.4 知识录入表单

- 所有 `Form.Item label` 改用 `getFieldLabel`
- 枚举字段改 `Select` + `getEnumOptions`（提交 value 仍为英文）
- 布尔 `Switch`：label 中文；旁注或 Select 显示「是/否」
- `is_template` / `is_immutable` / `winning_flag` / `need_parent_context` 保持 Switch，含义通过中文 label 表达
- JSON 文本域 label 中文化（如 `catalog_path` → `目录路径(JSON 数组)`）

---

## 8. 知识浏览页改造

### 8.1 筛选区折叠

**默认一行（收起）**：

| 字段 | 控件 |
|------|------|
| 分类 | Input |
| 知识类型 | Input |
| 状态 | Input |
| 关键词 | Input |
| — | 查询 / 重置 / **展开更多筛选** |

**展开后**追加：来源类型、产品、行业、地区、标签、安全级别、是否模板、中标标记、审核状态、生效/失效日期范围、筛选方案（选择/保存/删除）。

展开状态可用组件内 `useState`；不要求持久化。

### 8.2 列表

- 列名全部 `getFieldLabel`
- `status`、`knowledge_type` 列：`Tag` + `getEnumLabel`

---

## 9. 知识详情页改造

### 9.1 基础信息

- `Descriptions.Item label` 全部 `getFieldLabel`
- 枚举字段：`getEnumLabel`；布尔：`formatBoolean`
- `embedding_status`：保留 Tag 配色，文案用 `getEnumLabel`

### 9.2 内容

- 替换 `<pre>` 为 `KnowledgeContentViewer`（含预览/源码切换，默认预览）
- 传入 `detail.content` + `detail.assets`

### 9.3 结构字段

- label 中文化
- `tags` / `products` / `industries` / `customer_types` / `regions`：有值时渲染 `Tag` 列表；空显示 `-`
- `catalog_path` / `variables` / `exclusion_rules`：保留 JSON pre（复杂结构），仅 label 中文

### 9.4 关联资产

- 元数据 label 中文化
- 预览区继续 `renderAsset`
- 卡片标题：`{资产类型中文} #{id}`（image→图片，table→表格）

---

## 10. 依赖变更

`frontend/package.json` 新增：

```json
"react-markdown": "^9.0.0",
"remark-gfm": "^4.0.0"
```

布局使用 Ant Design `Splitter`（已有 `antd@^5.28.0`），不新增 resizable 库。

---

## 11. 错误处理与边界

| 场景 | 处理 |
|------|------|
| Markdown 解析异常 | 降级为 `<pre>` 展示原文 |
| 资产 `char_start` 缺失 | 排在正文块末尾 |
| 未知枚举值 | 显示原英文 |
| Splitter 拖到极限 | `min` 约束，不崩溃 |
| localStorage 不可用 | 静默忽略，用默认比例 |

---

## 12. 测试

| 用例 | 文件 |
|------|------|
| `buildContentBlocks` 纯文本 / 文中插图 / 无位置资产 / 表格资产 | `buildContentBlocks.test.ts` |
| `getFieldLabel` / `getEnumLabel` / `getEnumOptions` 关键枚举 | `knowledgeChunkMeta.test.ts` |

使用现有 vitest 环境；不新增 E2E。

---

## 13. 验收标准

1. 录入页章节预览默认看到格式化正文与内联图片/表格，可切源码。
2. 录入页两处 Splitter 可拖拽，刷新后比例恢复（同浏览器）。
3. 顶部文档选择占一行，无独立 Card。
4. 录入表单字段名与枚举选项均为中文，提交 payload 枚举值仍为英文。
5. 浏览页筛选默认一行 4 字段，展开后完整筛选可用。
6. 浏览列表列名中文，枚举列显示中文 Tag。
7. 详情页内容默认格式化预览，基础信息与结构字段 label 中文。
