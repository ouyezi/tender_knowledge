# Quickstart: 标书目录提取质量增强

**Feature**: `specs/005-outline-extraction-quality`  
**Purpose**: 验证伪标题过滤、质量摘要 API、鼎信回归指标与树形展示

**Depends on**: Epic 3（`specs/004-actual-bid-candidates`）已可用；P0 `parent_id` 修复已合入

## Prerequisites

- 服务已启动：`./scripts/start.sh`
- KB 与鼎信导入（或新上传 actual_bid docm）

```bash
export KB_ID="8a27ac63-50c5-401f-998e-200649a94ca5"
export OP=admin
```

## 场景 1：查看待确认任务质量摘要（P1）

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/tasks?status=ready&page_size=10" \
  -H "X-Operator-Id: ${OP}" | python3 -m json.tool
```

**期望**:

- `items` 仅含 `task_phase=full_pipeline` 且无 `error_message` 的条目
- 每项含 `file_name`、`outline_quality.node_count`、`outline_quality.l1_ratio`
- 若有质量风险，`outline_quality.warnings` 非空

## 场景 2：鼎信文档 — 节点数下降与真章节保留（SC-001 / SC-004）

**前置**: 鼎信餐补标书已导入并触发解析（或 `force_reparse`）

```bash
export BID_OUTLINE_ID="<bid_outline_id>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/bid-outlines/${BID_OUTLINE_ID}/nodes" \
  -H "X-Operator-Id: ${OP}" | python3 -c "
import json,sys
nodes=json.load(sys.stdin)['data']['nodes']
print('count', len(nodes))
print('l1', sum(1 for n in nodes if n['level']==1))
print('with_parent', sum(1 for n in nodes if n.get('parent_id')))
golden=['一、报价表格式','二、参选响应函','1.参选人业绩']
for g in golden:
    print(g, 'OK' if any(g in n['title'] for n in nodes) else 'MISSING')
"
```

**期望（增强后）**:

- `count` ≤ 302（较基线 432 减少 ≥30%）
- `with_parent` > 0（多数非根节点有 parent_id）
- golden 标题均为 `OK`

## 场景 3：质量摘要详情（任务级）

```bash
export PARSE_TASK_ID="<parse_task_id>"

curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/tasks/${PARSE_TASK_ID}" \
  -H "X-Operator-Id: ${OP}" | python3 -c "
import json,sys
d=json.load(sys.stdin)['data']
q=d.get('outline_quality') or {}
print('strategy', q.get('extract_strategy'))
print('filter_stats', q.get('filter_stats'))
print('warnings', q.get('warnings'))
"
```

**期望**: `filter_stats.by_reason` 含 `body_list_item` / `date_line` 等；`warnings` 与文档质量一致。

## 场景 4：目录详情树形层级（SC-002）

1. 浏览器打开 `http://127.0.0.1:5173/outlines/${BID_OUTLINE_ID}`
2. 检查左侧目录树存在 L2/L3 缩进，非全部平铺为 L1

**期望**: 子章节显示在父章节下；Tag 显示 L2、L3 等。

## 场景 5：确认向导质量警告（P1 UI）

1. 目录中心点击「去确认」进入向导
2. 若 `warnings` 含 `high_l1_ratio` 或 `flat_fallback`，顶部应显示 Alert

## 场景 6：自动化测试

```bash
cd backend && ../.venv/bin/pytest \
  tests/unit/test_outline_heading_filter.py \
  tests/unit/test_outline_quality_service.py \
  tests/integration/test_actual_bid_outline_quality.py \
  -v
```

**期望**: 全部通过；鼎信集成测试在本地有 docm 时执行，否则 skip。

## 场景 7：脏任务不出现（FR-012）

失败任务（`error_message` 非空）不应出现在 ready 列表：

```bash
curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/actual-bid-parse/tasks?status=ready" \
  -H "X-Operator-Id: ${OP}" | python3 -c "
import json,sys
items=json.load(sys.stdin)['data']['items']
bad=[i for i in items if i.get('error_message')]
print('dirty_ready', len(bad))
"
```

**期望**: `dirty_ready 0`

## 相关文档

- [spec.md](./spec.md)
- [data-model.md](./data-model.md)
- [contracts/outline-quality-api.md](./contracts/outline-quality-api.md)
- Epic 3 [quickstart](../004-actual-bid-candidates/quickstart.md)
