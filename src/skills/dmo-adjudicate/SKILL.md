---
name: dmo-adjudicate
description: 裁决外部（另一个模型、另一套系统、一份报告）给出的引用和结论是不是成立。当用户粘进来一段别的 AI 生成的糖尿病建议要你核、问「这句引文是不是真的」「这个哈希对不对」「这条结论站不站得住」「他引的原文能不能支撑这个结论」，或要做纯 LLM 与本体方案的对抗比对时使用。本 skill 规定了硬前置（先读 /adjudicate/scope）、引用五档与结论四档判定值的原样解释规则、诊断切点与管理目标必须分开裁决的口径，以及硬性禁令（不返回布尔、不接受自然语言 claim、not-adjudicable 与 unsupported 都不等于错）。Use when adjudicating externally supplied citations or clinical claims against this repository's ontology and verbatim source passages.
license: 与本仓库同许可
compatibility: 需要本仓库的 dmo 服务在 124.223.18.44:8100 可达（uv run dmo serve）；`/adjudicate/citations` 只依赖 GraphDB，`/adjudicate/claim` 还需要 PostgreSQL
allowed-tools: Bash(curl:*) Bash(uv:*) Read
metadata:
  repo: diabetes-ontology-agent
  version: "1.0"
---

# 引用与结论裁决

## 这个 skill 在优化什么

**不产生任何一枚印章。**

裁决族最大的误用是被当成"过了就是对的"。本仓库任何路径都不返回 `reasonable` /
`valid` / `passed` 这类布尔字段 —— 返回"已通过本体校验"，等于给外部系统发一枚
它承担不起的印章。31 条可引用出处、10 条计分风险规则，这个体量支撑不了任何
"全面校验"的说法。

所以你的输出永远是**分档的判定值 + 它的确切含义**，不是"通过/不通过"。

## 硬禁令

1. **不返回布尔。** 不写"这条结论是对的/错的""校验通过"。只给 verdict 值并解释它。
2. **不接受自然语言 claim。** `/adjudicate/claim` 只吃结构化断言。用户给的是一段话时，
   **把它拆成结构化字段并向用户确认**，不要自己解析完就当确定性结果用 ——
   一旦用模型解析，`adjudicationHash` 守住的确定性当场丢光。缺字段就问。
3. **`not-adjudicable` 是常见返回值，不是异常，更不是"没问题"。** 它的含义是
   "这类断言本体压根不管"。
4. **`unsupported` 是证据不足，不等于"判定为错"。** 这两件事必须分开说。
5. **`fabricated` 不是道德判断。** 严格含义是"本库 31 条可引用出处里没有逐字对应" ——
   也可能引自本仓库未收录的资料。不要说成"对方造假"。
6. **`supported` 只表示与当前 `graphVersion` 和规则集一致**，不是诊疗背书。
7. **`assertedBy` 只记账，绝不参与判定。** 谁说的不影响对不对。
8. **裁决值不得压缩。** 五档引用值和四档结论值必须原样给出，不许合并成两档。

## 调用约定

服务基址 `http://124.223.18.44:8100`（`uv run dmo serve --port 8100` 启动，只绑 127.0.0.1）。
**本 skill 不带封装脚本** —— 下面每条都是可直接粘贴的完整 curl，因此这四件事由你自己负责：

1. **连不上 ≠ 没有数据。** curl 报 `Connection refused` ⟹ 服务没起，先启动它，或全程
   改用 `uv run dmo …` CLI（**与 API 走同一份 `query/hybrid.py`，答案必然一致**）。
   **绝不因为够不着服务就改用常识作答。**
2. **必须看 HTTP 状态码**，别把 `{"detail":"…"}` 当数据读。排查时加
   `-w '\n-- HTTP %{http_code} --\n'`。
3. **POST 必须带 `-H 'Content-Type: application/json'`**，body 形状见各阶段示例。
4. 状态码分支：

   | 码 | 含义与处置 |
   |---|---|
   | **400** | claim 结构不合法，或该类型不在 `/adjudicate/scope` 的 `available` 列表里。先读 scope，**不要改个字段名重试** |
   | **404** | 患者不存在。裁决端点**刻意不返回看着像"没问题"的空结论** |
   | **422** | 参数类型不合法 |
   | **503** | GraphDB 不可用 ⟹ 三个裁决端点全停 |
   | **500** | PG 断连时只影响 `/adjudicate/claim`；`/adjudicate/citations` 不碰 PG，照常可用 |

## 阶段 0 · 先读 scope（不可跳过）

```bash
curl -sS http://localhost:8100/adjudicate/scope
```

调用任何裁决端点之前必须先读它。三件事：

- `adjudicable[].status` —— `available` / `planned`。**只有 available 的类型才能裁。**
  当前 6 类全 available：`Citation` `Assessment` `TargetAttainment` `Diagnosis`
  `RiskTier` `MedicationSafety`。
- `notAdjudicable` —— 剂量、概率与时间窗、个体化治疗决策、糖尿病域外、指南原文之外的共识。
  用户的问题落在这里，**直接回答判不了并给出 `why`，不要去试端点**。
- `corpus` —— 同时给「收录了多少份指南」和「多少份真的拿得出逐字出处」。
  当前 **32 份收录、只有 6 份贡献了那 31 条出处**。
  ⚠️ **别拿收录份数当覆盖面**，回答里报的是后者。

## 阶段 1 · 裁决引用：这句话是不是真的

完全确定性 —— 不需要患者、不碰 PostgreSQL、不跑规则链。

```bash
curl -sS -X POST http://124.223.18.44:8100/adjudicate/citations \
  -H 'Content-Type: application/json' \
  -d '{"citations":[
      {"quote":"6.5% or above","sha256":"96495c7d…"},
      {"quote":"6.5 percent or higher","sha256":"96495c7d…"},
      {"quote":"根据指南，通常认为血糖偏高即可诊断糖尿病"}],
    "assertedBy":"external-llm/some-model"}'
```

五个判定值，两两不相交，**逐条原样解释**：

| verdict | 含义 | 怎么向用户表述 |
|---|---|---|
| `verbatim` | 引文逐字命中，哈希相符 | 唯一一个「引用成立」。但成立 ≠ 用对了地方（见阶段 2 的 `misattributed`） |
| `hash-only` | **哈希是真的，引文被改写过** | ★ 最该抓的一类。明说"这条出处真实存在，但引文措辞被改动过" |
| `quote-only` | 引文对、哈希不对 | 哈希是编的，或指向了别的出处 —— 返回体会点名是哪一条 |
| `not-verbatim` | 与某条出处存在**包含关系**（截取或加话），哈希未命中 | 说清是截取还是加话，不要笼统说"不准确" |
| `fabricated` | 引文与哈希都无对应 | 照禁令 5 的口径表述 |

### `hash-only` 是这个端点存在的理由

引用真实存在、但在转述中被悄悄改了措辞 ——
**纯字符串比对抓不到**（引文和库里任何一条都不相同），
**纯哈希比对也抓不到**（哈希确实存在）。必须两条线一起看才会暴露。
这是 LLM 最典型的错法，**用户拿别的模型的输出来核时，优先看这一档有没有命中**。

### 为什么不做模糊匹配

没有编辑距离、没有 trigram、没有 embedding。相似度 0.87 判成"引用成立"，
等于用一个数字把伪造洗白。包含关系是纯机械可判定的，所以留着 —— 它能把
"改写/截取"与"凭空编造"分开。用户问"能不能宽松一点匹配"时，照这条解释拒绝。

## 阶段 2 · 裁决结论：这条结论站不站得住

```bash
curl -sS -X POST http://124.223.18.44:8100/adjudicate/claim \
  -H 'Content-Type: application/json' \
  -d '{"patientId":"P90002",
    "claim":{"type":"Diagnosis",
             "value":{"kind":"Diabetes","verificationStatus":"Confirmed"}},
    "assertedBy":"external-llm/some-model"}'
```

四个判定值：

| verdict | 含义 |
|---|---|
| `supported` | 本体按同一套规则推出了同一条结论 |
| `contradicted` | 语义键上冲突 —— 读 `comparison.conflicts` 逐条给出「声称值 → 系统值」 |
| `unsupported` | 既拿不出支撑也拿不出反驳。**证据不足与「判定为错」是两回事** |
| `not-adjudicable` | 本体压根不管这类断言。**常见返回值，不是异常** |

`contradicted` 时必须同时给 `missingEvidence` —— 它说清"差什么"，比判定值本身有用。
上面那条实测返回 `contradicted`，`missingEvidence` 是：

> 另一采样日的复测 —— 所用诊断切点 `confirmationRequired=true`，
> 单次落在区间内 ≠ 确诊。

**这是整套 API 最有说服力的一次比对。** A1C 落在糖尿病区间，纯 LLM 会说"是糖尿病"，
字符串匹配也会说"是糖尿病"；本体说的是"Provisional，还差一次复测"。
用户做对抗演示时，这条就是主线。

### ⚠️ 诊断切点与管理目标必须分开裁决

两类结论都是 `dmo:Assessment`、都进同一个模板，**只有 `ruleId` 能区分**：

| claim type | ruleId | 回答的问题 |
|---|---|---|
| `Assessment` | `LAB-THRESHOLD-MATCH` | 按诊断切点看，这个值落在哪个区间 |
| `TargetAttainment` | `TARGET-ATTAINMENT` | 按管理目标看，这个已确诊患者达没达标 |

一个 A1C 6.8% 的已确诊患者：按诊断切点是「超标」（≥6.5），按管理目标是「达标」（<7%）——
同一个数，两个相反的结论，因为它们回答的根本不是同一个问题。
实测 P90003 同时有 `High`（管理目标）与 `DiabetesRange`（诊断切点）两条结论。
**用户给的 claim 没说清是哪一类时，问他，不要替他选** —— 选错了判出来的对错是随机的。

### `misattributed` —— 引对了话，用错了地方

`claim` 请求里带上 `citations` 会额外做一层核查：**引文逐字属实，但不在支撑这条结论
的出处里**，标 `misattributed`。拿 FPG 的切点原文（`126 mg/dL or above`）去支撑一条
A1C 结论就会命中。

纯字符串比对抓不到（引文是真的），纯哈希比对也抓不到（哈希是真的）——
要靠 `thresholdCitesPassage` 的边反查它到底支撑了什么。
**核别的模型的输出时，`citations` 一定要一起传**，否则漏掉的正是这一类。

### `adjudicationHash`

`sha256(claim ‖ patientId ‖ graphVersion ‖ rulesFingerprint)`。同一条断言、同一版知识层
与规则集，跑一百次同哈希。`assertedBy` 与 `citations` **不进哈希** —— 谁说的、引了什么，
都不改变本体自己推出来的那条结论。

用户质疑"你这裁决稳不稳"时：同一请求连发 5 次，给 5 个相同的 `adjudicationHash`。

## 阶段 3 · 输出

```
【裁决对象】<原样复述被裁决的引用/结论 + assertedBy（若给了）>
【裁决范围】<本次落在 scope 的哪一类；若部分落在 notAdjudicable，先说这部分判不了及 why>
【引用】<逐条：verdict + 该档的确切含义 + 返回体给的 reason；hash-only / misattributed 单独点出>
【结论】<verdict + comparison.conflicts 逐条「声称 → 系统」+ missingEvidence>
【确定性】adjudicationHash <前 16 位>；同一断言与同一版知识层重复裁决结果不变
【边界】<corpus 的实际弹药量：N 条可引用出处、M 条计分规则；不足以支撑"全面校验">
⚠️ <disclaimer 原文>
```

字段级请求/返回体细节见 [references/endpoints.md](references/endpoints.md)。

## 交付前自检

- [ ] 调裁决端点之前读了 `/adjudicate/scope`？
- [ ] 有没有出现"通过/不通过""这条是对的"这类布尔表述？
- [ ] `not-adjudicable` 有没有被我说成"没问题"？`unsupported` 有没有被说成"错"？
- [ ] `fabricated` 的表述有没有变成指控对方造假？
- [ ] 五档引用值和四档结论值有没有被我压缩合并？
- [ ] `Assessment` 与 `TargetAttainment` 分清了吗，还是我替用户选了一个？
- [ ] 核外部模型输出时，`citations` 传了吗（否则漏掉 `misattributed`）？
- [ ] `supported` 有没有被我说成"医学上正确"？
- [ ] 报覆盖面时报的是"拿得出逐字出处的份数"，不是"收录份数"？
- [ ] `disclaimer` 带上了吗？

## 什么时候**不要**用这个 skill

- 用户问的是自己库里某个患者判成什么 → skill `dmo-patient-graph-analysis`。
- 用户问的是"这条结论凭什么"（自家结论的溯源，不是裁决外部结论）→ skill `dmo-provenance-trace`。
- 用户要裁决剂量、概率、时间窗、治疗方案、糖尿病域外的断言 → 照 `notAdjudicable` 的
  `why` 回答判不了，**不要去试端点**。
- 用户要一个"总分"或"可信度百分比" → 拒绝。本模块任何路径都不产生标量评分。
