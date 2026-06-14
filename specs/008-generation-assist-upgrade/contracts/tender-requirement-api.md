# API Contract: Tender Requirement Context

**Base path**: `/api/v1/kbs/{kb_id}/tender-requirements`  
**Version**: 1.0.0 (Epic 6)

**说明**: 外部招标约束为服务层输入对象，**非**知识库内部资产；不参与检索索引。
Header: `X-Operator-Id`（审计）。

---

## POST /

创建招标约束上下文。

**Body**:

```json
{
  "title": "XX 智慧园区项目招标约束",
  "outline_structure": { "max_level": 3, "numbering_style": "decimal" },
  "outline_nodes": [
    { "title": "1. 技术方案", "level": 1, "sort_order": 0 },
    { "title": "1.1 总体架构", "level": 2, "sort_order": 1 }
  ],
  "score_points": [
    { "node_ref": "1.1 总体架构", "text": "架构清晰、可扩展，响应时间≤2秒" }
  ],
  "rejection_clauses": ["未提供资质证明废标", "方案未响应星号条款废标"],
  "format_requirements": ["目录须三级编号", "A4 竖版"],
  "qualification_requirements": ["ISO9001 证书", "同类项目业绩≥3个"],
  "response_clauses": ["须逐条响应技术规格书"],
  "source_note": "人工录入自招标文件 PDF"
}
```

**Response `data`**:

```json
{
  "requirement_context_id": "uuid",
  "title": "XX 智慧园区项目招标约束",
  "status": "active",
  "created_at": "2026-06-14T10:00:00Z"
}
```

---

## GET /{requirement_context_id}

查询单条招标约束详情。

**Response `data`**: 完整字段 + `created_by`, `updated_at`。

---

## GET /

列表查询。

**Query**: `status` (active|archived), `q` (title 模糊), `page`, `page_size`

---

## PATCH /{requirement_context_id}

更新招标约束（全量或部分字段）。

**Body**: 同 POST 字段子集 + `status`

**Note**: 已关联 Generation Snapshot 的上下文 SHOULD 保留历史；更新后新建议/生成使用新版本，
旧 snapshot 内 `requirement_context_snapshot` 不变。

---

## POST /{requirement_context_id}/archive

归档（软删除），`status → archived`。

**Errors**:

| Code | HTTP | When |
|------|------|------|
| NOT_FOUND | 404 | requirement_context_id 不存在 |
| INVALID_OUTLINE | 422 | outline_nodes 为空或缺少 title |
