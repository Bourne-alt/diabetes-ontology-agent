#!/usr/bin/env bash
# dmo 融合查询 API 的薄封装。做三件 curl 不替你做的事：
#   1. 连不上时给出可执行的补救命令，而不是一句 Connection refused
#   2. 非 2xx 时打印状态码 + body，避免把 404 的 {"detail":...} 当成数据读
#   3. POST 模板时挡下空患者数组（API 会 400，但错在客户端，早点说）
#
# 用法：
#   dmo-get.sh /health
#   dmo-get.sh '/patients?icd10=E11&size=5'
#   dmo-get.sh /patients/P90002/assessment
#   dmo-get.sh -X POST /query/care_chain '["P90002","P90003"]'
#   dmo-get.sh -X POST /patients/P90002/simulate \
#     '{"assume":[{"term":"A1C","value":7.9,"unit":"percent","date":"2026-02-20"}]}'
#
# 基址：DMO_BASE，默认 http://localhost:8000（服务仅绑 127.0.0.1）
set -uo pipefail

BASE="${DMO_BASE:-http://localhost:8000}"

usage() { sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }

METHOD=GET
if [[ "${1:-}" == "-X" ]]; then
  METHOD="${2:-}"; shift 2
fi
[[ $# -ge 1 ]] || usage 2
[[ "$1" == "-h" || "$1" == "--help" ]] && usage 0

PATH_="$1"; BODY="${2:-}"
[[ "$PATH_" == /* ]] || PATH_="/$PATH_"

# 两类 POST，body 形状不同，早点分流才能给对错误提示。
IS_SIMULATE=0
[[ "$PATH_" == */simulate ]] && IS_SIMULATE=1

if [[ "$METHOD" == "POST" ]]; then
  if [[ $IS_SIMULATE == 1 ]]; then
    # 推演的 body 是对象不是数组。空 assume 会 400 —— 刻意的：
    # 没有假设事实的推演等同于重算基线，那该走 GET /patients/{pid}。
    if [[ -z "$BODY" || "$BODY" != \{* ]]; then
      echo "错误：POST $PATH_ 需要形如" >&2
      echo "  '{\"assume\":[{\"term\":\"A1C\",\"value\":7.9,\"unit\":\"percent\",\"date\":\"2026-02-20\"}]}'" >&2
      echo "假设值必须显式给出 —— 系统不生成候选值（这是推演不是预测）。" >&2
      exit 2
    fi
  else
    # 空数组会返回 400 —— 刻意的，空结果和"没给患者"长得一模一样。
    if [[ -z "$BODY" || "$BODY" == "[]" ]]; then
      echo "错误：POST $PATH_ 需要非空的患者号数组，如 '[\"P90002\"]'" >&2
      echo "模板不做全库扫描 —— 先用 GET /patients 收敛出患者集合。" >&2
      exit 2
    fi
  fi
fi

TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT

if [[ "$METHOD" == "POST" ]]; then
  CODE=$(curl -sS -m 30 -o "$TMP" -w '%{http_code}' \
              -X POST -H 'Content-Type: application/json' \
              -d "$BODY" "$BASE$PATH_" 2>"$TMP.err") || CODE=000
else
  CODE=$(curl -sS -m 30 -o "$TMP" -w '%{http_code}' "$BASE$PATH_" 2>"$TMP.err") || CODE=000
fi

if [[ "$CODE" == "000" ]]; then
  echo "连不上 $BASE —— 先确认服务在跑：" >&2
  echo "  uv run dmo serve --port 8000" >&2
  echo "或全程改用 CLI（同一条代码路径）：uv run dmo show <患者号>" >&2
  [[ -s "$TMP.err" ]] && sed 's/^/  curl: /' "$TMP.err" >&2
  rm -f "$TMP.err"; exit 1
fi
rm -f "$TMP.err"

# 尽量美化；不是 JSON 就原样吐出（错误页、空 body 等）
if ! python3 -m json.tool --no-ensure-ascii < "$TMP" 2>/dev/null; then
  cat "$TMP"; echo
fi

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
    404) echo "   患者不存在，或模板名不在白名单。GET /query/templates 看可用模板。" >&2 ;;
    422) echo "   参数类型不合法（FastAPI 校验）。" >&2 ;;
    500) echo "   PG / GraphDB 可能断连。先跑：dmo-get.sh /health" >&2 ;;
  esac
  exit 1
fi
