#!/usr/bin/env bash
# Epic 4 quickstart verification on 鼎信餐补标书.docm data
set -euo pipefail

KB_ID="${KB_ID:-8a27ac63-50c5-401f-998e-200649a94ca5}"
OP="${OP:-admin}"
IMPORT_ID="${IMPORT_ID:-54e467b9-c3e0-454b-91f8-c47299eae610}"
REAL_DOC="${REAL_DOC:-/Users/tongqianni/xlab/标书助力/测试招投标文件/标书诊断/鼎信/鼎信餐补标书.docm}"
BASE="http://127.0.0.1:8000/api/v1/kbs/${KB_ID}"

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

echo "=== 前置: 鼎信餐补标书.docm ==="
echo "  文档路径: ${REAL_DOC}"
[[ -f "$REAL_DOC" ]] && check "本地 docm 存在" 1 || check "本地 docm 存在" 0

IMPORT_DETAIL=$(curl -s "${BASE}/file-imports/${IMPORT_ID}" -H "X-Operator-Id: ${OP}")
FILE_NAME=$(echo "$IMPORT_DETAIL" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['file_name'])" 2>/dev/null || echo "")
IMPORT_STATUS=$(echo "$IMPORT_DETAIL" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])" 2>/dev/null || echo "")
check "导入记录存在 ($FILE_NAME status=$IMPORT_STATUS)" "$([[ "$FILE_NAME" == *"鼎信餐补"* && "$IMPORT_STATUS" == "confirmed" ]] && echo 1 || echo 0)"

echo "=== 前置: 生成 pending 候选（章节分类回填 + candidate_generate）==="
BOOT=$(cd "$(dirname "$0")/.." && .venv/bin/python scripts/bootstrap-dingxin-candidates.py)
echo "$BOOT"
CREATED=$(echo "$BOOT" | awk -F= '/^created_candidates=/{print $2}')
PENDING_BOOT=$(echo "$BOOT" | awk -F= '/^pending_candidates=/{print $2}')
TAXONOMY_ID=$(echo "$BOOT" | awk -F= '/^ku_taxonomy_id=/{print $2}')
CATEGORY_ID=$(echo "$BOOT" | awk -F= '/^category_id=/{print $2}')
check "候选就绪 created=$CREATED pending=$PENDING_BOOT" "$([[ "${PENDING_BOOT:-0}" -gt 0 ]] && echo 1 || echo 0)"

echo "=== 场景0: pending 候选存在 ==="
PENDING_TOTAL=$(curl -s "${BASE}/candidates?status=pending" -H "X-Operator-Id: ${OP}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['total'])")
check "pending total=$PENDING_TOTAL" "$([[ "$PENDING_TOTAL" -ge 3 ]] && echo 1 || echo 0)"

echo "=== 场景1: 按 import_id 筛选 ==="
FILTERED=$(curl -s "${BASE}/candidates?status=pending&import_id=${IMPORT_ID}&chapter_taxonomy_id=${TAXONOMY_ID}" \
  -H "X-Operator-Id: ${OP}")
FILTER_COUNT=$(echo "$FILTERED" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data']['items']))")
FIRST_ID=$(echo "$FILTERED" | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[0]['candidate_id'] if items else '')")
check "筛选命中 count=$FILTER_COUNT" "$([[ "$FILTER_COUNT" -ge 1 ]] && echo 1 || echo 0)"

CANDIDATE_ID="$FIRST_ID"
SECOND_ID=$(echo "$FILTERED" | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[1]['candidate_id'] if len(items)>1 else '')")
THIRD_ID=$(echo "$FILTERED" | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[2]['candidate_id'] if len(items)>2 else '')")
MERGE_SOURCE=$(echo "$FILTERED" | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[3]['candidate_id'] if len(items)>3 else '')")
IGNORE_ID=$(echo "$FILTERED" | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[-1]['candidate_id'] if items else '')")

echo "=== 场景2: 编辑候选 ==="
PATCH=$(curl -s -X PATCH "${BASE}/candidates/${CANDIDATE_ID}" \
  -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
  -d '{"title":"鼎信-修订标题","summary":"鼎信 quickstart 修订摘要"}')
PATCH_STATUS=$(echo "$PATCH" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])" 2>/dev/null || echo "")
check "PATCH 后仍 pending (got $PATCH_STATUS)" "$([[ "$PATCH_STATUS" == "pending" ]] && echo 1 || echo 0)"

echo "=== 场景3: 发布为 KU ==="
CONFIRM=$(curl -s -X POST "${BASE}/candidates/${CANDIDATE_ID}/confirm" \
  -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
  -d "{
    \"confirm_as\": \"ku\",
    \"product_category_ids\": [\"${CATEGORY_ID}\"],
    \"chapter_taxonomy_id\": \"${TAXONOMY_ID}\",
    \"knowledge_type\": \"solution\",
    \"searchable\": true,
    \"review_comment\": \"鼎信 quickstart 单条发布\"
  }")
PUB_STATUS=$(echo "$CONFIRM" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('status',''))" 2>/dev/null || echo "")
OBJECT_ID=$(echo "$CONFIRM" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('confirmed_object_id',''))" 2>/dev/null || echo "")
check "发布成功 status=$PUB_STATUS object=$OBJECT_ID" "$([[ "$PUB_STATUS" == "published" && -n "$OBJECT_ID" ]] && echo 1 || echo 0)"

echo "=== 场景4: 忽略候选 ==="
if [[ -n "$IGNORE_ID" && "$IGNORE_ID" != "$CANDIDATE_ID" ]]; then
  IGNORE=$(curl -s -X POST "${BASE}/candidates/${IGNORE_ID}/confirm" \
    -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
    -d '{"confirm_as":"ignore","review_comment":"鼎信低价值忽略"}')
  IGNORE_STATUS=$(echo "$IGNORE" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])" 2>/dev/null || echo "")
  check "忽略 status=$IGNORE_STATUS" "$([[ "$IGNORE_STATUS" == "rejected" ]] && echo 1 || echo 0)"
else
  check "忽略（跳过，候选不足）" 1
fi

echo "=== 场景5: 合并候选 ==="
if [[ -n "$SECOND_ID" && -n "$MERGE_SOURCE" && "$SECOND_ID" != "$MERGE_SOURCE" ]]; then
  MERGE=$(curl -s -X POST "${BASE}/candidates/merge" \
    -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
    -d "{
      \"target_candidate_id\": \"${SECOND_ID}\",
      \"source_candidate_ids\": [\"${MERGE_SOURCE}\"],
      \"review_comment\": \"鼎信重复段落合并\"
    }")
  MERGED=$(echo "$MERGE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('merged_count',0))" 2>/dev/null || echo "0")
  check "合并 merged_count=$MERGED" "$([[ "$MERGED" == "1" ]] && echo 1 || echo 0)"
else
  check "合并（跳过，候选不足）" 1
fi

echo "=== 场景6: 批量确认 ==="
BATCH_ITEMS=$(curl -s "${BASE}/candidates?status=pending&import_id=${IMPORT_ID}&page_size=5" -H "X-Operator-Id: ${OP}" \
  | python3 -c "
import json,sys
items=json.load(sys.stdin)['data']['items'][:2]
payload=[]
for i, it in enumerate(items):
    if i == 0:
        payload.append({'candidate_id': it['candidate_id'], 'confirm_as':'ku','knowledge_type':'solution','product_category_ids':['${CATEGORY_ID}'],'chapter_taxonomy_id':'${TAXONOMY_ID}'})
    else:
        payload.append({'candidate_id': it['candidate_id'], 'confirm_as':'ignore'})
print(json.dumps(payload))
")
BATCH=$(curl -s -X POST "${BASE}/candidates/batch/confirm" \
  -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
  -d "{\"items\": ${BATCH_ITEMS}, \"batch_comment\": \"鼎信 quickstart batch\"}")
BATCH_ID=$(echo "$BATCH" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('batch_id',''))" 2>/dev/null || echo "")
BATCH_OK=$(echo "$BATCH" | python3 -c "import json,sys; d=json.load(sys.stdin).get('data',{}); print(int(d.get('succeeded',0))+int(d.get('failed',0)))" 2>/dev/null || echo "0")
check "批量 batch_id=$BATCH_ID processed=$BATCH_OK" "$([[ -n "$BATCH_ID" && "$BATCH_OK" -ge 1 ]] && echo 1 || echo 0)"

echo "=== 场景7: 审计日志 ==="
AUDIT=$(curl -s "${BASE}/candidate-audit-logs?candidate_id=${CANDIDATE_ID}" -H "X-Operator-Id: ${OP}")
ACTIONS=$(echo "$AUDIT" | python3 -c "import json,sys; print(','.join(i['action'] for i in json.load(sys.stdin)['data']['items']))" 2>/dev/null || echo "")
check "审计含 publish (actions=$ACTIONS)" "$(echo "$ACTIONS" | grep -q publish && echo 1 || echo 0)"

echo "=== 场景8: 发布失败重试（合成校验失败）==="
RETRY_CAND=$(curl -s "${BASE}/candidates?status=pending&import_id=${IMPORT_ID}&page_size=1" -H "X-Operator-Id: ${OP}" \
  | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[0]['candidate_id'] if items else '')")
if [[ -n "$RETRY_CAND" ]]; then
  curl -s -X POST "${BASE}/candidates/${RETRY_CAND}/confirm" \
    -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
    -d '{"confirm_as":"manual_asset","title":"鼎信测试资产"}' > /dev/null
  RETRY=$(curl -s -X POST "${BASE}/candidates/${RETRY_CAND}/retry-publish" \
    -H "Content-Type: application/json" -H "X-Operator-Id: ${OP}" \
    -d "{\"confirm_as\":\"ku\",\"knowledge_type\":\"solution\",\"product_category_ids\":[\"${CATEGORY_ID}\"],\"chapter_taxonomy_id\":\"${TAXONOMY_ID}\"}")
  RETRY_STATUS=$(echo "$RETRY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('status',''))" 2>/dev/null || echo "")
  RETRY_AUDIT=$(curl -s "${BASE}/candidate-audit-logs?candidate_id=${RETRY_CAND}" -H "X-Operator-Id: ${OP}" \
    | python3 -c "import json,sys; print(','.join(i['action'] for i in json.load(sys.stdin)['data']['items']))" 2>/dev/null || echo "")
  check "重试发布 status=$RETRY_STATUS" "$([[ "$RETRY_STATUS" == "published" ]] && echo 1 || echo 0)"
  check "审计含 publish_failed (actions=$RETRY_AUDIT)" "$(echo "$RETRY_AUDIT" | grep -q publish_failed && echo 1 || echo 0)"
else
  check "重试（跳过，无 pending 候选）" 1
  check "publish_failed 审计（跳过）" 1
fi

echo "=== 场景9: 检索隔离 ==="
PENDING_SAMPLE=$(curl -s "${BASE}/candidates?status=pending&import_id=${IMPORT_ID}&page_size=1" -H "X-Operator-Id: ${OP}" \
  | python3 -c "import json,sys; items=json.load(sys.stdin)['data']['items']; print(items[0]['candidate_id'].replace('doc_','') if items else '')")
if [[ -n "$PENDING_SAMPLE" ]]; then
  LEAK=$(curl -s "${BASE}/knowledge-units?status=published" -H "X-Operator-Id: ${OP}" \
    | python3 -c "import json,sys; cid='${PENDING_SAMPLE}'; print(len([i for i in json.load(sys.stdin)['data']['items'] if i.get('candidate_id')==cid]))")
  check "pending 候选未出现在正式 KU (leak=$LEAK)" "$([[ "$LEAK" == "0" ]] && echo 1 || echo 0)"
else
  check "检索隔离（跳过，无 pending 样本）" 1
fi

echo ""
echo "========== 汇总: ${pass} 通过, ${fail} 失败 =========="
echo "IMPORT_ID=$IMPORT_ID CANDIDATE_ID=$CANDIDATE_ID"
echo "UI: http://127.0.0.1:5173/candidates?import_id=${IMPORT_ID}"
echo "审计: http://127.0.0.1:5173/candidates/audit"
exit "$fail"
