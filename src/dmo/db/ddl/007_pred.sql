-- 007 · L4 风险分层的 SQL 物化
--
-- ⚠️ 这两张表**不做任何判定**，只是把 51-risk-stratification.rq 在 GraphDB 里
--   算出来的结论抄下来。判定逻辑只有一份，在规则文件里。
--   在 SQL 里再实现一遍"顺手"的分层，就会有两套规则慢慢分叉，
--   而且没人知道 API 返回的是哪一套。
--
-- 抄下来的理由是查询效率：/patients 列表要按 tier 筛选分页，
-- 每次去 GraphDB 跑一遍分层规则不现实。

CREATE TABLE IF NOT EXISTS diabetes.pred_risk_stratification (
    patientid           text PRIMARY KEY,
    tier                text NOT NULL,
    rule_id             text NOT NULL,
    rule_version        text NOT NULL,
    insufficient_reason text,
    monitoring_gap      text,
    factor_count        integer NOT NULL DEFAULT 0,
    caveat              text NOT NULL,
    computed_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pred_tier_ck CHECK (tier IN
        ('High','Moderate','Low','Insufficient-Evidence'))
);

COMMENT ON CONSTRAINT pred_tier_ck ON diabetes.pred_risk_stratification IS
    'tier 是**有序枚举，不是分数**。CHECK 约束在 schema 层面堵死"顺手加个 0-100 评分"'
    '——那个数字一旦存在，就会被当成概率读，而它不是。';
COMMENT ON COLUMN diabetes.pred_risk_stratification.insufficient_reason IS
    '为什么判不了。这是本项目最有价值的一列：15 个真实 E11 患者全部落在 '
    'Insufficient-Evidence，而这一列说清了是因为检验值不可信 + 无风险侧事实，'
    '而不是返回一个空集让人以为"没查到"。';

CREATE TABLE IF NOT EXISTS diabetes.pred_factor_hit (
    hit_id            text PRIMARY KEY,
    patientid         text NOT NULL,
    risk_rule_id      text NOT NULL,
    risk_factor_iri   text NOT NULL,
    risk_factor_label text,
    risk_category     text,
    trigger_basis     text NOT NULL,
    counted_in_tier   boolean NOT NULL,
    from_fact_iri     text,
    source_id         text,
    quote             text,
    sha256            text,
    external_note     text
);
CREATE INDEX IF NOT EXISTS pred_hit_patient_idx ON diabetes.pred_factor_hit (patientid);

COMMENT ON COLUMN diabetes.pred_factor_hit.counted_in_tier IS
    'false = 命中了但**不参与 tier 判定**，因为找不到可逐字引用的指南原文'
    '（ICD-HYPERTENSION / ICD-DYSLIPIDEMIA 就是这样）。'
    '它们仍然出现在返回体里 —— 让缺口可见，而不是假装这个风险因子不存在。';
COMMENT ON COLUMN diabetes.pred_factor_hit.sha256 IS
    '所引 SourcePassage 的内容哈希。counted_in_tier=true 的行这一列必须非空 ——'
    '「列不出出处的因子不参与判定」这条规矩的可执行断言。';
COMMENT ON COLUMN diabetes.pred_factor_hit.external_note IS
    'trigger_basis=external-standard 时说明数值边界从哪来。'
    '例如 BMI≥25 来自 WHO 定义，**不在**本仓库语料中 —— 用户看到的是'
    '「Being overweight（CDC 原文）+ 判定用的 25 来自 WHO」，'
    '而不是一个假装什么都有出处的结论。';
