#!/usr/bin/env python3
"""病程轨迹跑批 —— 前缀累加地调用 /patients/{pid}/simulate，逐步给出结论变化。

    第 1 步：基线 + 假设[0]
    第 2 步：基线 + 假设[0..1]
    ...

⚠️ 轨迹**不是链式演化**。服务端每次调用都从同一个真实基线重新跑两遍规则链
（runner.py 每次新建 Dataset），所以每一步的 before 恒等于基线。第 k 步的含义是
"基线 + 前 k 条假设"，不是"第 k−1 步之后又发生了什么"。把它叙述成"病情逐步进展"
是拿平行假设冒充时间演化 —— SKILL.md 禁令 5。

之所以要前缀累加而不是一次性注入全部：30 号规则数的是 distinct 采样日期，
"第几条假设让 Provisional 翻成 Confirmed" 这个问题只有逐步跑才答得出来；
一次性注入只能告诉你终点，答不出临界点在哪。

只用标准库 —— 远端环境不保证有 requests / jq。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# API 侧硬上限（hypothesis.parse）。超了服务端会拒，早点在客户端说。
MAX_ASSUME = 10
# SKILL.md 阶段 E 的探针预算。超了不是报错，是提醒你该停下交回用户。
BUDGET_HINT = 4


def parse_spec(spec: str) -> dict:
    """`TERM:VALUE:UNIT:DATE` → 假设事实。四段缺一不可 —— 缺单位的数值在临床上
    没有意义（148 是 mg/dL 还是 mmol/L 结论天差地别），缺日期则 30 号规则数不出
    distinct 天数。这里不做任何默认填充。"""
    parts = spec.split(":")
    if len(parts) != 4:
        sys.exit(f"假设格式错误：{spec!r}\n应为 TERM:VALUE:UNIT:DATE，"
                 "例如 A1C:6.5:percent:2026-02-20（四段都不能省）")
    term, value, unit, date = (p.strip() for p in parts)
    try:
        num = float(value)
    except ValueError:
        sys.exit(f"{term} 的 value {value!r} 不是数值。")
    return {"term": term, "value": num, "unit": unit, "date": date}


def post(base: str, pid: str, assume: list[dict], timeout: int) -> dict:
    req = urllib.request.Request(
        f"{base.rstrip('/')}/patients/{pid}/simulate",
        data=json.dumps({"assume": assume}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        detail = body
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            pass
        print(f"-- HTTP {e.code} --\n{detail}", file=sys.stderr)
        if e.code == 400:
            print("\n↑ 这句拒绝理由**就是答案**，照抄给用户。"
                  "不要换个术语名或换个单位重试 —— 本系统不猜术语、不默认单位。",
                  file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.exit(f"连不上 {base}：{e.reason}\n"
                 "这是接入问题不是数据问题：确认 DMO_BASE 可达、部署方已暴露服务。"
                 "拿不到就停下如实报告，不要改用猜测回答。")


def fmt_delta(delta: list[dict]) -> list[str]:
    """结论级 diff 的可读化。只播报 changed 的受关注字段 ——
    三元组级差异噪声压倒信号，注入一条假设就会多出几十条。"""
    out = []
    for d in delta:
        kind, change = d.get("type"), d.get("change")
        if change == "changed":
            for f, v in (d.get("fields") or {}).items():
                out.append(f"    ~ {kind}.{f}: {v.get('before')} → {v.get('after')}")
        elif change == "added":
            a = d.get("after") or {}
            label = (a.get("conclusion") or a.get("diagnosisKind")
                     or a.get("tier") or a.get("severity") or "")
            extra = a.get("thresholdId") or a.get("verificationStatus") or ""
            out.append(f"    + {kind}: {label} {extra}".rstrip())
        elif change == "removed":
            b = d.get("before") or {}
            label = (b.get("conclusion") or b.get("diagnosisKind")
                     or b.get("tier") or b.get("severity") or "")
            out.append(f"    − {kind}: {label}（结论消失，少见，需单独说明）")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="前缀累加的病程轨迹推演（确定性；不写 GraphDB 一个字节）")
    ap.add_argument("pid")
    ap.add_argument("assume", nargs="+", metavar="TERM:VALUE:UNIT:DATE",
                    help="假设事实，按注入顺序给出；值只能来自用户原话或本体阈值区间端点")
    ap.add_argument("--base", default=os.environ.get("DMO_BASE", ""))
    ap.add_argument("--repeat", type=int, default=1,
                    help="对完整假设集重复推演 N 次，验证 derivationHash 恒定")
    ap.add_argument("--tree", action="store_true", help="额外输出末步 derivationTree 的 JSON")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()
    # 行缓冲：错误走 stderr、轨迹走 stdout，不行缓冲的话 400 的报错会插到表头前面，
    # 读起来像是"还没开始就失败了"。
    sys.stdout.reconfigure(line_buffering=True)

    if not args.base:
        sys.exit("DMO_BASE 未设置（也没给 --base）。本 skill 不回落 localhost："
                 "远端回落只会得到一串 Connection refused，看起来像服务挂了，实则是没配基址。")
    if len(args.assume) > MAX_ASSUME:
        sys.exit(f"一次最多 {MAX_ASSUME} 条假设事实，收到 {len(args.assume)} 条（API 侧硬上限）。")

    specs = [parse_spec(s) for s in args.assume]
    if len(specs) > BUDGET_HINT:
        print(f"⚠️ 探针预算提示：本次 {len(specs)} 步，超过单目标建议上限 {BUDGET_HINT} 步。"
              "无预算的搜索会滑成「调到出现想要的结论为止」。\n", file=sys.stderr)

    print(f"患者 {args.pid} · 轨迹 {len(specs)} 步（每步 = 基线 + 前 k 条假设，"
          "非链式演化）\n")

    last = None
    for k in range(1, len(specs) + 1):
        res = post(args.base, args.pid, specs[:k], args.timeout)
        last = res
        added = specs[k - 1]
        print(f"步 {k}｜+ {added['term']} {added['value']} {added['unit']} @{added['date']}")
        print(f"  derivationHash {res['derivationHash'][:16]}  graphVersion {res['graphVersion']}")
        for h in res.get("hypotheticalFacts", []):
            if h.get("conversionNote"):
                print(f"    ⇄ {h['conversionNote']}")
        if res.get("unchanged"):
            print("  unchanged: true —— 这一步没有改变任何结论。**是结论不是故障。**")
        else:
            print("  delta:")
            for line in fmt_delta(res.get("delta") or []):
                print(line)
        print()

    if args.repeat > 1:
        hashes = {post(args.base, args.pid, specs, args.timeout)["derivationHash"]
                  for _ in range(args.repeat)}
        verdict = "全部相同 ✅" if len(hashes) == 1 else f"出现 {len(hashes)} 个不同哈希 ❗"
        print(f"确定性复核：完整假设集连推 {args.repeat} 次，{verdict}")
        for h in sorted(hashes):
            print(f"  {h[:16]}")
        if len(hashes) > 1:
            print("  哈希不一致只有三种可能：假设变了、本体改了、规则改了。"
                  "本次假设未变 ⟹ 服务端知识层或规则集在推演期间被改动，此前结论全部作废。")
        print()

    if last and args.tree:
        print("末步 derivationTree（每个 LabResult 的 provenance 必须在回答里逐条标出）：")
        print(json.dumps(last.get("derivationTree"), ensure_ascii=False, indent=2))
        print()

    if last:
        print(last.get("hypotheticalNote", ""))
        print(last.get("disclaimer", ""))


if __name__ == "__main__":
    main()
