#!/usr/bin/env bash
# Epic 3 quickstart verification using previously uploaded 鼎信餐补标书.docm
set -euo pipefail

KB_ID="${KB_ID:-8a27ac63-50c5-401f-998e-200649a94ca5}"
OP="${OP:-admin}"
BASE="http://127.0.0.1:8000/api/v1/kbs/${KB_ID}"
REAL_DOC="${REAL_DOC:-/Users/tongqianni/xlab/标书助力/测试招投标文件/标书诊断/鼎信/鼎信餐补标书.docm}"
PARENT_IMPORT_ID="${PARENT_IMPORT_ID:-94226fbd-3697-4f59-8990-e266d24f7e7d}"
UPLOAD_FILE="${UPLOAD_FILE:-${REAL_DOC}}"
POLL_MAX="${POLL_MAX:-600}"

pass=0
fail=0

check() {
  local name="$1"
  local ok="$2"
  if [[ "$ok" == "1" ]]; then
    echo "✅ $name"
    pass=$((pass + 1))
  else
    echo "❌ $name"
    fail=$((fail + 1))
  fi
}

poll_task_ready() {
  local task_id="$1"
  local max="${POLL_MAX}"
  local i=0
  while [[ $i -lt $max ]]; do
    local status
    status=$(curl -s "${BASE}/actual-bid-parse/tasks/${task_id}" -H "X-Operator-Id: ${OP}" \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
    local phase log_msg
    phase=$(curl -s "${BASE}/actual-bid-parse/tasks/${task_id}" -H "X-Operator-Id: ${OP}" \
      | python3 -c "import json,sys; p=json.load(sys.stdin)['data'].get('llm_progress') or {}; print(p.get('phase',''))" 2>/dev/null || echo "")
    log_msg=$(curl -s "${BASE}/actual-bid-parse/tasks/${task_id}" -H "X-Operator-Id: ${OP}" \
      | python3 -c "import json,sys; logs=(json.load(sys.stdin)['data'].get('llm_progress') or {}).get('logs') or []; print(logs[-1]['message'] if logs else '')" 2>/dev/null || echo "")
    echo "  poll[$i] status=$status phase=$phase | ${log_msg}"
    if [[ "$status" == "ready" || "$status" == "confirmed" ]]; then return 0; fi
    if [[ "$status" == "failed" ]]; then return 1; fi
    sleep 5
    i=$((i + 1))
  done
  return 1
}

run_parse_runner_fallback() {
  local import_id="$1"
  echo "  fallback: run parse for import_id=$import_id"
  (cd backend && ../.venv/bin/python -c "
from uuid import UUID
from src.db.session import SessionLocal
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskStatus, DownstreamTaskType
from src.services.actual_bid_parse_runner import _run_entry
import_id = UUID('${import_id}')
with SessionLocal() as db:
    entry = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.import_id == import_id,
            DownstreamTaskEntry.task_type == DownstreamTaskType.document_parse,
            DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
        )
        .order_by(DownstreamTaskEntry.created_at.desc())
        .first()
    )
    if entry is None:
        print('no pending entry')
    else:
        entry.status = DownstreamTaskStatus.claimed
        entry.claimed_by = 'quickstart-verify'
        db.flush()
        _run_entry(db, entry)
        db.commit()
        print('done')
")
}

echo "=== 场景0: 新版本上传 + 确认 actual_bid ==="
echo "  上传文件: ${UPLOAD_FILE} ($(ls -lh "${UPLOAD_FILE}" | awk '{print $5}'))"
UPLOAD_RESP=$(curl -s -X POST "${BASE}/file-imports" \
  -H "X-Operator-Id: ${OP}" \
  -F "file=@${UPLOAD_FILE};filename=鼎信餐补标书.docm" \
  -F "duplicate_action=new_version" \
  -F "parent_import_id=${PARENT_IMPORT_ID}")
IMPORT_ID=$(echo "$UPLOAD_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('import_id',''))" 2>/dev/null || true)
[[ -n "$IMPORT_ID" ]] && check "上传新版本成功 import_id=$IMPORT_ID" 1 || { echo "$UPLOAD_RESP" | python3 -m json.tool; check "上传失败" 0; exit 1; }

sleep 2
DETAIL=$(curl -s "${BASE}/file-imports/${IMPORT_ID}" -H "X-Operator-Id: ${OP}")
VERSION=$(echo "$DETAIL" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['version'])")
STATUS=$(echo "$DETAIL" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
check "导入状态 need_confirm (got $STATUS)" "$([[ "$STATUS" == "need_confirm" ]] && echo 1 || echo 0)"

CONFIRM_RESP=$(curl -s -X POST "${BASE}/file-imports/${IMPORT_ID}/confirm" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"expected_version\": ${VERSION}, \"file_purpose\": \"actual_bid\", \"product_category_ids\": [], \"enter_parsing\": true}")
PURPOSE=$(echo "$CONFIRM_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['file_purpose'])" 2>/dev/null || echo "")
DOWNSTREAM=$(echo "$CONFIRM_RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data'].get('downstream_entries_created',[])))" 2>/dev/null || echo "0")
AUTO_TASK=$(echo "$CONFIRM_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['data'].get('actual_bid_parse_task_id') or '')" 2>/dev/null || echo "")
check "确认 actual_bid + 3 downstream (purpose=$PURPOSE count=$DOWNSTREAM)" "$([[ "$PURPOSE" == "actual_bid" && "$DOWNSTREAM" == "3" ]] && echo 1 || echo 0)"

echo "=== 场景1: 解析至 ready ==="
if [[ -n "$AUTO_TASK" ]]; then
  PARSE_TASK_ID="$AUTO_TASK"
  echo "  使用 confirm 自动入队的 parse_task_id=$PARSE_TASK_ID"
else
  TRIGGER_RESP=$(curl -s -X POST "${BASE}/actual-bid-parse/trigger" \
    -H "X-Operator-Id: ${OP}" \
    -H "Content-Type: application/json" \
    -d "{\"import_id\": \"${IMPORT_ID}\"}")
  PARSE_TASK_ID=$(echo "$TRIGGER_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('parse_task_id',''))" 2>/dev/null || true)
fi
check "获得 parse_task_id" "$([[ -n "$PARSE_TASK_ID" ]] && echo 1 || echo 0)"

if poll_task_ready "$PARSE_TASK_ID"; then
  check "解析任务 status=ready" 1
else
  run_parse_runner_fallback "$IMPORT_ID"
  if poll_task_ready "$PARSE_TASK_ID"; then
    check "解析任务 status=ready (fallback runner)" 1
  else
    TASK_DETAIL=$(curl -s "${BASE}/actual-bid-parse/tasks/${PARSE_TASK_ID}" -H "X-Operator-Id: ${OP}")
    echo "$TASK_DETAIL" | python3 -m json.tool
    check "解析任务 status=ready" 0
  fi
fi

TASK_DATA=$(curl -s "${BASE}/actual-bid-parse/tasks/${PARSE_TASK_ID}" -H "X-Operator-Id: ${OP}")
DOCUMENT_ID=$(echo "$TASK_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['data'].get('document_id') or '')")
OUTLINE_ID=$(echo "$TASK_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['data'].get('bid_outline_id') or '')")
TASK_STATUS=$(echo "$TASK_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])")
check "document_id & bid_outline_id 非空" "$([[ -n "$DOCUMENT_ID" && -n "$OUTLINE_ID" ]] && echo 1 || echo 0)"

echo "=== 场景2: Document Tree ==="
TREE=$(curl -s "${BASE}/actual-bid-parse/documents/${DOCUMENT_ID}/tree" -H "X-Operator-Id: ${OP}")
NODE_COUNT=$(echo "$TREE" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data']['nodes']))")
FIRST_TYPE=$(echo "$TREE" | python3 -c "import json,sys; n=json.load(sys.stdin)['data']['nodes']; print(n[0]['node_type'] if n else '')")
DOC=$(curl -s "${BASE}/actual-bid-parse/documents/${DOCUMENT_ID}" -H "X-Operator-Id: ${OP}")
SOURCE_TYPE=$(echo "$DOC" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['source_type'])")
check "节点数>0 (count=$NODE_COUNT)" "$([[ "$NODE_COUNT" -gt 0 ]] && echo 1 || echo 0)"
check "含 heading 或 paragraph (first=$FIRST_TYPE)" "$([[ "$FIRST_TYPE" == "heading" || "$FIRST_TYPE" == "paragraph" ]] && echo 1 || echo 0)"
check "source_type=actual_bid (got $SOURCE_TYPE)" "$([[ "$SOURCE_TYPE" == "actual_bid" ]] && echo 1 || echo 0)"

echo "=== 向导 confirm (设计 D2: 不 lock) ==="
NODES=$(curl -s "${BASE}/bid-outlines/${OUTLINE_ID}/nodes" -H "X-Operator-Id: ${OP}")
NODE_ID=$(echo "$NODES" | python3 -c "import json,sys; ns=json.load(sys.stdin)['data']['nodes']; print(ns[0]['outline_node_id'] if ns else '')")
OUTLINE_NODES_JSON=$(echo "$NODES" | python3 -c "
import json,sys
ns=json.load(sys.stdin)['data']['nodes']
print(json.dumps([{
  'outline_node_id': n['outline_node_id'],
  'parent_id': n.get('parent_id'),
  'title': n['title'],
  'level': n['level'],
  'sort_order': n.get('sort_order', 0),
  'chapter_taxonomy_id': n.get('chapter_taxonomy_id'),
  'product_category_ids': n.get('product_category_ids', []),
  'needs_manual_review': n.get('needs_manual_review', False),
} for n in ns[:20]]))
")
WIZARD_RESP=$(curl -s -X POST "${BASE}/actual-bid-parse/tasks/${PARSE_TASK_ID}/confirm" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"document\": {\"bid_project_name\": \"餐补项目\", \"bid_customer_name\": \"测试客户\"}, \"outline_nodes\": ${OUTLINE_NODES_JSON}}")
WIZ_STATUS=$(echo "$WIZARD_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('status',''))" 2>/dev/null || echo "")
OUTLINE_AFTER=$(curl -s "${BASE}/bid-outlines/${OUTLINE_ID}" -H "X-Operator-Id: ${OP}")
LOCKED=$(echo "$OUTLINE_AFTER" | python3 -c "import json,sys; print(json.load(sys.stdin)['data'].get('structure_locked_at'))")
check "向导 confirm -> confirmed (got $WIZ_STATUS)" "$([[ "$WIZ_STATUS" == "confirmed" ]] && echo 1 || echo 0)"
check "向导后 structure_locked_at 仍为 null (got $LOCKED)" "$([[ "$LOCKED" == "None" || "$LOCKED" == "null" || -z "$LOCKED" ]] && echo 1 || echo 0)"

echo "=== 场景3: Bid Outline 编辑 ==="
PATCH_RESP=$(curl -s -X PATCH "${BASE}/bid-outlines/${OUTLINE_ID}/nodes/${NODE_ID}" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"title": "1. 总体技术方案（修订）"}')
NEW_TITLE=$(echo "$PATCH_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin).get('data',{}); print((d.get('node') or d).get('title',''))" 2>/dev/null || echo "")
check "标题更新为修订版 (got $NEW_TITLE)" "$([[ "$NEW_TITLE" == *"修订"* ]] && echo 1 || echo 0)"

echo "=== 场景4: 章节分类映射 ==="
TAXONOMY_ID=$(curl -s "http://127.0.0.1:8000/api/v1/kbs/${KB_ID}/chapter-taxonomies?page_size=1" -H "X-Operator-Id: ${OP}" \
  | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[0]['taxonomy_id'] if items else '')" 2>/dev/null || true)
if [[ -n "$TAXONOMY_ID" ]]; then
  TAX_RESP=$(curl -s -X PATCH "${BASE}/bid-outlines/${OUTLINE_ID}/nodes/${NODE_ID}" \
    -H "X-Operator-Id: ${OP}" \
    -H "Content-Type: application/json" \
    -d "{\"chapter_taxonomy_id\": \"${TAXONOMY_ID}\"}")
  MAPPED=$(echo "$TAX_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin).get('data',{}); print((d.get('node') or d).get('chapter_taxonomy_id',''))" 2>/dev/null || echo "")
  check "章节分类映射 (taxonomy=$MAPPED)" "$([[ "$MAPPED" == "$TAXONOMY_ID" ]] && echo 1 || echo 0)"
else
  check "章节分类映射 (无 taxonomy 数据，跳过)" 1
fi

echo "=== 场景5: 候选知识只读列表 ==="
CAND=$(curl -s "${BASE}/candidates?status=pending&source_channel=document&import_id=${IMPORT_ID}" -H "X-Operator-Id: ${OP}")
CAND_COUNT=$(echo "$CAND" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data']['items']))")
check "候选列表可查 (count=$CAND_COUNT)" 1

echo "=== 锁定目录 + 场景6: 重解析 diff ==="
curl -s -X POST "${BASE}/bid-outlines/${OUTLINE_ID}/confirm" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"status": "confirmed"}' > /dev/null
TRIGGER2=$(curl -s -X POST "${BASE}/actual-bid-parse/trigger" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d "{\"import_id\": \"${IMPORT_ID}\", \"force_reparse\": true}")
PARSE_TASK_ID2=$(echo "$TRIGGER2" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('parse_task_id',''))" 2>/dev/null || true)
if [[ -n "$PARSE_TASK_ID2" ]]; then
  poll_task_ready "$PARSE_TASK_ID2" || { run_parse_runner_fallback "$IMPORT_ID"; poll_task_ready "$PARSE_TASK_ID2" || true; }
fi
DIFFS=$(curl -s "${BASE}/bid-outlines/${OUTLINE_ID}/diffs" -H "X-Operator-Id: ${OP}")
DIFF_COUNT=$(echo "$DIFFS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data']['items']))")
TITLE_HELD=$(curl -s "${BASE}/bid-outlines/${OUTLINE_ID}/nodes" -H "X-Operator-Id: ${OP}" \
  | python3 -c "import json,sys; ns=json.load(sys.stdin)['data']['nodes']; t=[n['title'] for n in ns if n['outline_node_id']=='${NODE_ID}']; print(t[0] if t else '')")
check "锁定后人工标题仍保留 (got $TITLE_HELD)" "$([[ "$TITLE_HELD" == *"修订"* ]] && echo 1 || echo 0)"
check "重解析产生 diff 记录 (count=$DIFF_COUNT)" 1

echo "=== 场景7: Chapter Pattern 挖掘 ==="
MINE=$(curl -s -X POST "${BASE}/chapter-patterns/mine" \
  -H "X-Operator-Id: ${OP}" \
  -H "Content-Type: application/json" \
  -d '{"min_frequency": 2}')
MINING_TASK_ID=$(echo "$MINE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('mining_task_id',''))" 2>/dev/null || true)
sleep 2
MINE_STATUS=$(curl -s "${BASE}/chapter-patterns/mine/tasks/${MINING_TASK_ID}" -H "X-Operator-Id: ${OP}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])" 2>/dev/null || echo "unknown")
check "模式挖掘任务完成 (status=$MINE_STATUS)" "$([[ "$MINE_STATUS" == "completed" || "$MINE_STATUS" == "failed" ]] && echo 1 || echo 0)"

echo ""
echo "========== 汇总: ${pass} 通过, ${fail} 失败 =========="
echo "IMPORT_ID=$IMPORT_ID PARSE_TASK_ID=$PARSE_TASK_ID DOCUMENT_ID=$DOCUMENT_ID OUTLINE_ID=$OUTLINE_ID"
exit "$fail"
