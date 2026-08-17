#!/usr/bin/env bash
# dmo 融合查询 API 的远端薄封装。做四件 curl 不替你做的事：
#   1. DMO_BASE 未设置时**当场停下**，而不是回落 localhost —— 远端回落只会
#      得到一串 Connection refused，看起来像"服务挂了"，实则是没配基址。
#   2. 非 2xx 时打印状态码 + body，避免把 404 的 {"detail":...} 当数据读。
#   3. simulate 的 body 是对象不是数组，两类 POST 早点分流才能给对错误提示。
#   4. 400 时提示"照抄 detail，不要改名重试" —— 那句拒绝理由本身就是答案。
#
# 用法：
#   export DMO_BASE=https://<部署地址>
#   dmo.sh /health
#   dmo.sh '/patients?icd10=E11&size=5'
#   dmo.sh /patients/P90002
#   dmo.sh -X POST /query/care_chain '["P90002","P90003"]'
#   dmo.sh -X POST /patients/P90002/simulate \
#     '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
set -uo pipefail

if [[ -z "${DMO_BASE:-}" ]]; then
  cat >&2 <<'EOF'
错误：环境变量 DMO_BASE 未设置。

本 skill 面向远端智能体，**不假设服务在 localhost**（dmo serve 默认只绑 127.0.0.1，
远端可达与否取决于部署方是否显式暴露）。请先：

  export DMO_BASE=https://<你的部署地址>

拿不到基址时，正确做法是如实报告"远端够不着这套服务"并停下，
不要改用猜测回答 —— 本仓库的立身之本是可追责，不是"看起来答上了"。
EOF
  exit 2
fi

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }

METHOD=GET
if [[ "${1:-}" == "-X" ]]; then METHOD="${2:-}"; shift 2; fi
[[ $# -ge 1 ]] || usage 2
[[ "$1" == "-h" || "$1" == "--help" ]] && usage 0

PATH_="$1"; BODY="${2:-}"
[[ "$PATH_" == /* ]] || PATH_="/$PATH_"

IS_SIMULATE=0
[[ "$PATH_" == */simulate ]] && IS_SIMULATE=1

if [[ "$METHOD" == "POST" ]]; then
  if [[ $IS_SIMULATE == 1 ]]; then
    # 空 assume 会 400 —— 刻意的：没有假设事实的推演等同于重算基线，
    # 那该走 GET /patients/{pid}。
    if [[ -z "$BODY" || "$BODY" != \{* ]]; then
      echo "错误：POST $PATH_ 需要形如" >&2
      echo "  '{\"assume\":[{\"term\":\"A1C\",\"value\":7.9,\"unit\":\"percent\",\"date\":\"2026-02-20\"}]}'" >&2
      echo "假设值必须显式给出（用户原话，或本体阈值区间端点并标注出身）—— 系统不生成候选值。" >&2
      exit 2
    fi
  elif [[ -z "$BODY" || "$BODY" == "[]" ]]; then
    echo "错误：POST $PATH_ 需要非空的患者号数组，如 '[\"P90002\"]'" >&2
    echo "模板不做全库扫描 —— 先用 GET /patients 收敛出患者集合。" >&2
    exit 2
  fi
fi

TMP="$(mktemp)"; trap 'rm -f "$TMP" "$TMP.err"' EXIT

if [[ "$METHOD" == "POST" ]]; then
  CODE=$(curl -sS -m 60 -o "$TMP" -w '%{http_code}' \
              -X POST -H 'Content-Type: application/json' \
              -d "$BODY" "$DMO_BASE$PATH_" 2>"$TMP.err") || CODE=000
else
  CODE=$(curl -sS -m 60 -o "$TMP" -w '%{http_code}' "$DMO_BASE$PATH_" 2>"$TMP.err") || CODE=000
fi

if [[ "$CODE" == "000" ]]; then
  echo "连不上 $DMO_BASE —— 这是接入问题，不是数据问题。" >&2
  echo "确认基址可达、且部署方已把服务暴露给远端；拿不到就停下如实报告。" >&2
  [[ -s "$TMP.err" ]] && sed 's/^/  curl: /' "$TMP.err" >&2
  exit 1
fi

python3 -m json.tool --no-ensure-ascii < "$TMP" 2>/dev/null || { cat "$TMP"; echo; }

if [[ "$CODE" != 2* ]]; then
  echo "-- HTTP $CODE ($METHOD $PATH_) --" >&2
  case "$CODE" in
    400) if [[ $IS_SIMULATE == 1 ]]; then
           echo "   推演被拒。上面 detail 里的理由**就是答案**，照抄给用户 ——" >&2
           echo "   常见两类：术语没挂阈值（不猜术语）、单位缺失或无已核实换算系数。" >&2
           echo "   不要换个名字或换个单位重试。" >&2
         else
           echo "   模板拿到空患者数组。" >&2
         fi ;;
    404) echo "   患者不存在（或未 sync 进图库），或模板名不在白名单。" >&2 ;;
    422) echo "   参数类型不合法（FastAPI 校验）。" >&2 ;;
    500) echo "   服务端 PG / GraphDB 可能断连。先跑：dmo.sh /health" >&2 ;;
  esac
  exit 1
fi
