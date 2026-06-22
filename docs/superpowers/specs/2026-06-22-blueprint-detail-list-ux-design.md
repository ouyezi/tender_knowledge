# Design: 目录蓝图详情树交互与列表列宽优化

**Date**: 2026-06-22  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-21-directory-blueprint-design.md` · `docs/superpowers/specs/2026-06-22-directory-blueprint-generation-extraction-design.md`

---

## 1. 背景与问题

### 1.1 用户反馈

| # | 现象 | 期望 |
|---|------|------|
| 1 | 目录蓝图详情页看不到 V1.1 节点字段「应标/得分/应答提示」 | 点击目录节点后，右侧节点详情应展示 `content_description` 与 `tender_response_hint` |
| 2 | 蓝图列表页名称列宽度不稳定，标签/版本列占用过多 | 名称列固定宽度且可省略号展示；标签、版本等辅助列更紧凑 |

### 1.2 根因分析

**问题 1 — 非数据缺失，而是交互冲突**

- V1.1 字段（`content_description`、`tender_response_hint`）已在 `BlueprintNodeDetailPanel` 与后端 API 中实现。
- `BlueprintDetailPage` 只读模式通过 `BlueprintOutlineTreeReadonly` + `BlueprintNodeDetailPanel` 展示节点详情。
- `BlueprintOutlineTreeReadonly` 在节点标题 `<span>` 上绑定了 `onClick` + `event.stopPropagation()`，点击标题触发「章节标题已复制」，**阻止 Tree 的 `onSelect` 回调**，导致 `selectedPath` 始终为空，右侧始终显示「请选择目录节点查看详情」。
- 蓝图级 `suggested_structure_md` 已在详情页 `Descriptions` 中展示，用户确认可见。

**问题 2 — 列表列宽未调优**

- `BlueprintListPage` 中「蓝图名称」列无 `width`，随表格自动伸缩。
- 三列标签各 `width: 220`，版本 `width: 90`，名称列在宽屏下被挤压、窄屏下表现不一致。

---

## 2. 范围

### 2.1 包含

- 修复 `BlueprintOutlineTreeReadonly` 点击选中与复制交互
- 调整 `BlueprintListPage` 表格列宽与 Tag 尺寸

### 2.2 不包含

- 后端 API / 数据模型变更
- `BlueprintMetaForm`、`BlueprintDetailPage` 顶部 `Descriptions` 布局调整
- 详情页默认选中首节点（列为可选增强，本次不做）
- 录入页 `BlueprintOutlineTree`（可编辑树）交互变更

---

## 3. 方案决议

### 3.1 目录树交互（方案 A）

| 操作 | 行为 |
|------|------|
| 单击节点标题/行 | 选中节点 → 右侧展示节点详情（含应标提示） |
| 复制标题 | 标题旁独立复制图标按钮（`CopyOutlined`），点击复制并 Toast「章节标题已复制」 |

**不采用**：保留「点击标题即复制」并依赖点击行空白选中（命中区域小、易误触）。

### 3.2 列表列宽（方案 A）

固定名称列宽度，压缩标签与版本列；标签使用 `Tag size="small"`。

---

## 4. 详细设计

### 4.1 `BlueprintOutlineTreeReadonly.tsx`

**变更前**：标题 `onClick` 复制 + `stopPropagation`。

**变更后**：

```text
节点标题展示结构：
[章节标题（重要程度）] [复制图标]

- 标题区域：不拦截冒泡，由 Ant Design Tree 处理选中
- 复制图标：onClick + stopPropagation，仅图标点击触发复制
- 复制图标：Tooltip「复制章节标题」；`aria-label` 同上
- 键盘：Enter/Space 在图标上触发复制（保持可访问性）
```

**影响面**：`BlueprintDetailPage` 只读树、`BlueprintEditor` 在 `readOnly` 模式下的只读树，行为一致。

### 4.2 `BlueprintListPage.tsx`

| 列 | width | 其他 |
|----|-------|------|
| 蓝图名称 | 260 | `ellipsis`；链接按钮限制 `maxWidth: 100%`；`Tooltip` 悬停显示全文 |
| 来源章节 | 180 | `ellipsis` |
| 产品标签 | 140 | `Tag size="small"` |
| 行业标签 | 140 | 同上 |
| 场景标签 | 140 | 同上 |
| 状态 | 80 | `Tag size="small"` |
| 版本 | 64 | 文本居中（`align: "center"`） |
| 更新时间 | 180 | 不变 |
| 操作 | 90 | 不变 |

`renderTags`  helper 增加 `size="small"` 传给 `Tag`。

名称列 `render` 示例结构：

```tsx
<Tooltip title={record.name}>
  <Button type="link" size="small" style={{ maxWidth: "100%", ...ellipsisStyles }}>
    {record.name || "-"}
  </Button>
</Tooltip>
```

---

## 5. 测试策略

### 5.1 手工 Smoke

1. 打开已有蓝图的详情页（只读模式）→ 点击目录树任意节点 → 右侧出现「内容描述」「应标/得分/应答提示」表单项（有值则回显，无值则空 TextArea）。
2. 点击节点标题旁复制图标 → Toast「章节标题已复制」，且当前节点保持选中、右侧详情不变。
3. 蓝图列表页 → 名称列宽度稳定约 260px，长名称省略号；标签列更窄；版本列紧凑。
4. 录入页蓝图 Tab（若使用只读树）行为与详情页一致。

### 5.2 自动化（可选）

- 本次以前端交互微调为主，不强制新增单元测试。
- 若项目已有蓝图相关 E2E，可补充「详情页选节点 → 节点详情面板可见」断言。

---

## 6. 与既有设计对齐

| 原 V1 设计 | 本次调整 |
|------------|----------|
| 详情页「点击标题复制」 | 改为「点击选中 + 图标复制」，优先保证节点详情可达 |
| V1.1 节点字段在详情页只读展示 | 修复选中链路后自然满足，无需新增字段 UI |

---

## 7. 文件清单

| 文件 | 操作 |
|------|------|
| `frontend/src/components/Blueprint/BlueprintOutlineTreeReadonly.tsx` | 修改树交互 |
| `frontend/src/pages/Knowledge/BlueprintListPage.tsx` | 修改列宽与 Tag 尺寸 |
