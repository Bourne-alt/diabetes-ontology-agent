# 裁决族端点：请求与返回体字段

三个端点。读之前先确认 SKILL.md 的八条硬禁令，本文件只补字段细节。

---

## `GET /adjudicate/scope`

无参数。**调用其余两个端点之前必读。**

| 字段 | 读法 |
|---|---|
| `adjudicable[].type` / `.status` | `available` 才能裁。`planned` 是"还没实现"，**不是"判过了没问题"** |
| `adjudicable[].semanticKey` | 该类型按哪几个字段比对。你构造 claim 的 `value` 时必须覆盖这些键 |
| `notAdjudicable[].topic` / `.why` | 用户的问题命中这里 → 直接回答判不了并给出 `why`，**不试端点** |
| `corpus.sources` | 收录了多少份指南。**不要拿这个数当覆盖面** |
| `corpus.withPassages` | 其中多少份真的贡献了可逐字引用的出处。**报这个** |
| `graphVersion` | 同一会话里它变了 ⟹ 此前所有裁决结论作废，重跑 |

当前实测：6 类全 `available`（`Citation` `Assessment` `TargetAttainment` `Diagnosis`
`RiskTier` `MedicationSafety`）；32 份收录、**只有 6 份**贡献了那 31 条出处。

`adjudicable` 与代码里真正接线的 `adjudicate.claim.ADJUDICABLE` **有测试对齐** ——
以后加类型忘了改 scope，CI 会亮。

---

## `POST /adjudicate/citations`

### 请求

```jsonc
{
  "citations": [                       // 必填，最多 200 条
    {"quote": "6.5% or above",         // quote 与 sha256 至少给一个
     "sha256": "96495c7d…"},           // 只给 sha256 也能判（会命中 hash-only 一族）
    {"quote": "根据指南，通常认为血糖偏高即可诊断糖尿病"}
  ],
  "assertedBy": "external-llm/some-model"   // 选填，只记账，不参与判定
}
```

### 返回

| 字段 | 读法 |
|---|---|
| `results[].verdict` | 五档之一，见 SKILL.md 的表 |
| `results[].reason` | **判定理由的权威表述，原样转述给用户**，不要自己重写 |
| `results[].matched[]` | 命中的出处：`passageId` / `quote` / `sha256` / `trusted` |
| `summary` | 各档计数。批量核一份外部报告时先看它 |
| `checkedAgainst.passages` | 本次比对的出处总数（当前 31）。**报覆盖面时用它** |
| `checkedAgainst.verifiedBy` | `verify_passages.py`（quote 逐字回原文 + 哈希一致） |
| `untrustedMatches` | ⚠️ 命中了但**不在可信图**里的出处 id。非 null 时必须在回答里点出来，不能当成正常命中 |
| `note` | 说明 `verbatim` 的严格含义。结论段落里带上 |
| `graphVersion` / `disclaimer` | 原样带上 |

### 两个容易漏的点

- **只给 `quote` 不给 `sha256`** 也会判 `verbatim`，但 `reason` 里会写明"未提供 sha256"。
  转述时保留这句 —— 它意味着这次只核了引文没核哈希。
- 短于 8 个字符的引文**不做包含匹配**。`"6.5%"` 会被半数 passage 包含，报出来全是噪声，
  还会把 `fabricated` 误洗成 `not-verbatim`。用户拿极短片段来核时，说明这个限制。

---

## `POST /adjudicate/claim`

### 请求

```jsonc
{
  "patientId": "P90002",                    // 必填。患者不存在 → 404，不返回看着像"没问题"的空结论
  "claim": {
    "type": "Diagnosis",                    // 五类之一，见 scope 的 available 列表
    "value": {"kind": "Diabetes",           // 字段必须覆盖该类型的 semanticKey
              "verificationStatus": "Confirmed"}
  },
  "citations": [ … ],                       // 选填但强烈建议：不传就漏掉 misattributed
  "assertedBy": "external-llm/some-model"   // 选填，不进 adjudicationHash
}
```

⚠️ **`Assessment` 与 `TargetAttainment` 必须由调用方选定**，两者都是 `dmo:Assessment`，
只有 `ruleId` 能区分（`LAB-THRESHOLD-MATCH` / `TARGET-ATTAINMENT`）。用户没说清就问他。

### 返回（公共字段）

| 字段 | 读法 |
|---|---|
| `verdict` | 四档之一 |
| `verdictReason` | **判定理由的权威表述，原样转述** |
| `adjudicationHash` | `sha256(claim ‖ patientId ‖ graphVersion ‖ rulesFingerprint)`。`assertedBy` 与 `citations` 不进哈希 |
| `graphVersion` / `rulesFingerprint` | 哈希的两个输入。任一变化 ⟹ 结论需重裁 |
| `systemConclusions[]` | 本体自己推出来的那几条。即使 verdict 是 `unsupported` 也要看 |
| `comparison.semanticKey` / `.keysUsed` | 按哪几个键比的、实际用上了哪几个 |
| `comparison.conflicts[]` | `{systemConclusion, diffs}` —— 逐条给出「声称值 → 系统值」 |
| `citationCheck` | 传了 `citations` 才有。**`misattributed` 在这里出现**：引文逐字属实，但不在支撑这条结论的出处里 |
| `disclaimer` | 原样带上 |

### 按 verdict 分支的字段

| verdict | 额外字段 | 必须做的事 |
|---|---|---|
| `supported` | `basedOn` `evidence` **`supportedMeans`** | ⚠️ `supportedMeans` 明说"不代表临床上正确、不是任何形式的诊疗背书"，**必须原样带上** |
| `contradicted` | `missingEvidence` `evidence` | `missingEvidence` 说清差什么 —— 比判定值本身有用，单独成段 |
| `unsupported` | `missingEvidence` | 逐条给 `need` / `because` / `wouldChangeVerdictTo`。**证据不足 ≠ 判定为错** |
| `not-adjudicable` | `whyNotAdjudicable` | 原样转述。标着 `planned` 的类型不要当成"判过了没问题" |

### `unsupported` 最常见的两个原因

`missingEvidence[].because` 会指出来，照抄即可：

1. 上游值 `valueTrustLevel=Unverified`，被 `20-lab-assessment.rq` 挡在门外；
2. 该术语在映射表里 `verify_status` 不是 `verified`。

分不清是哪一种 → `GET /terms/explain?term=…`。

---

## 三个端点的依赖差异

| 端点 | GraphDB | PostgreSQL | 确定性 |
|---|---|---|---|
| `/adjudicate/scope` | ✅ | — | 随知识层版本变化 |
| `/adjudicate/citations` | ✅ | — | **完全确定性**，不跑规则链 |
| `/adjudicate/claim` | ✅ | ✅ | 同 `adjudicationHash` 输入则同结果 |

`/health` 里 `graphdb.ok=false` ⟹ 三个都停；`postgres.ok=false` ⟹ 只有 `claim` 停，
`citations` 照常可用。
