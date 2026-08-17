-- 003 · L2 术语对齐层
--
-- 这一层回答一个问题：上游的中文表面形式（'血糖'、'二甲双胍'、'E11'）
-- 对应本体里的哪个概念 IRI，以及**能不能用**。
--
-- 「能不能用」比「对应哪个」更重要。对照组 semantic_link 只做了前者：
-- 把「尿蛋白」用字符串相似度链到两个互斥的疾病，confidence 都写 0.9，
-- 没有单位、没有阈值、没有出处，也没有任何「这条不可用」的表达。
-- 本层的 verify_status / value_kind 就是为了让「不可用」成为一等公民。

-- ── 概念索引 ────────────────────────────────────────────────────────
-- 从 GraphDB 拉下来的只读投影，`dmo map sync-concepts` 幂等重建。
-- 存在 SQL 里的唯一理由：search_concept 要能对中文表面形式做 LIKE / trigram，
-- 纯 SPARQL 版查不到 —— 这个并集是术语层的核心。
CREATE TABLE IF NOT EXISTS diabetes.map_concept_ref (
    iri            text PRIMARY KEY,
    concept_kind   text NOT NULL,
    code           text,
    label          text,
    alt_labels     text[] NOT NULL DEFAULT '{}',
    unit_canonical text,
    graph_version  text NOT NULL,
    synced_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS map_concept_kind_idx ON diabetes.map_concept_ref (concept_kind);

COMMENT ON COLUMN diabetes.map_concept_ref.graph_version IS
    '同步时知识层文件的内容哈希。映射行记录了它当时对齐的 graph_version，'
    '本体改了以后可以查出哪些映射指向了已删/已改的概念 —— 悬空的映射不报错，'
    '只是静默失效，必须有办法查出来。';

-- ── 检验项目映射（核心）────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.map_lab_term (
    id             bigserial PRIMARY KEY,
    src_name       text NOT NULL,
    src_ref_range  text,
    concept_iri    text REFERENCES diabetes.map_concept_ref(iri),
    -- 单位换算：只在 ETL 做，SPARQL 里一次都不做
    unit_src       text,
    unit_target    text,
    conv_factor    numeric,
    conv_offset    numeric NOT NULL DEFAULT 0,
    value_kind     text NOT NULL,
    trust_default  text NOT NULL DEFAULT 'Unverified',
    verify_status  text NOT NULL DEFAULT 'candidate',
    note           text,
    verified_by    text,
    verified_at    timestamptz,
    UNIQUE (src_name, src_ref_range),
    CONSTRAINT map_lab_term_value_kind_ck
        CHECK (value_kind IN ('quantitative', 'qualitative', 'unusable')),
    CONSTRAINT map_lab_term_trust_ck
        CHECK (trust_default IN ('Attested', 'Curated', 'Unverified')),
    CONSTRAINT map_lab_term_status_ck
        CHECK (verify_status IN ('verified', 'candidate', 'rejected',
                                 'unmappable', 'no-source-data')),
    -- 换算系数必须人工核实过才准填。推断出来的系数直接生效 = 用推断冒充断言。
    CONSTRAINT map_lab_term_conv_needs_verify
        CHECK (conv_factor IS NULL OR verify_status = 'verified')
);
CREATE INDEX IF NOT EXISTS map_lab_term_name_idx ON diabetes.map_lab_term (src_name);

COMMENT ON COLUMN diabetes.map_lab_term.src_ref_range IS
    '上游参考范围。原表**没有单位列**，这是推断单位的唯一线索（血糖 3.9-6.1 ⟹ mmol/L）。'
    '同一个项目名配不同参考范围可能是不同单位，所以它进了唯一键。';
COMMENT ON COLUMN diabetes.map_lab_term.value_kind IS
    'quantitative=可作数值判定；qualitative=定性项（参考范围写“阴性”），'
    '**永不进 core_lab_result**，只进 core_observation.value_text；'
    'unusable=连定性都读不出。';
COMMENT ON COLUMN diabetes.map_lab_term.verify_status IS
    'verified=人工核实，正常映射；candidate/rejected=跳过并计数；'
    'unmappable=结构上无法映射；no-source-data=概念存在但上游全库没有这个项目'
    '（A1C 就是这种：本体里有，真实库一条数值都没有）。'
    '后两者会进 API 返回体的 unmapped[]，由 explain_gap() 如实回答“为什么查不到”。';

-- ── ICD-10 映射 ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.map_icd10 (
    icd10code     text PRIMARY KEY,
    icd10name     text,
    concept_iri   text REFERENCES diabetes.map_concept_ref(iri),
    concept_kind  text NOT NULL,
    verify_status text NOT NULL DEFAULT 'candidate',
    note          text,
    CONSTRAINT map_icd10_kind_ck
        CHECK (concept_kind IN ('DiabetesType', 'Complication', 'Comorbidity', 'Unrelated')),
    CONSTRAINT map_icd10_status_ck
        CHECK (verify_status IN ('verified', 'candidate', 'rejected', 'unmappable'))
);

COMMENT ON COLUMN diabetes.map_icd10.concept_kind IS
    'Unrelated 是刻意保留的取值：上游 24 个 ICD-10 码里大部分（中耳炎、阑尾炎、偏头痛）'
    '与糖尿病无关。显式标成 Unrelated，好过留空让人猜是“还没映射”还是“不该映射”。';

-- ── 药名映射 ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.map_drug_term (
    src_name        text PRIMARY KEY,
    medication_iri  text REFERENCES diabetes.map_concept_ref(iri),
    drug_class_iri  text REFERENCES diabetes.map_concept_ref(iri),
    is_antidiabetic boolean NOT NULL DEFAULT false,
    verify_status   text NOT NULL DEFAULT 'candidate',
    note            text,
    CONSTRAINT map_drug_status_ck
        CHECK (verify_status IN ('verified', 'candidate', 'rejected', 'unmappable'))
);

-- ── 风险规则的 SQL 侧投影 ───────────────────────────────────────────
-- 判定仍在 SPARQL（51-risk-stratification.rq）。这里只存一份供 API 解释用：
-- 返回体要说明「这条因子的数值边界来自 WHO 而非本仓库语料」，
-- 每次都去 GraphDB 取太啰嗦。
CREATE TABLE IF NOT EXISTS diabetes.map_risk_rule (
    risk_rule_id      text PRIMARY KEY,
    label             text,
    observed_kind     text NOT NULL,
    observed_code     text,
    match_value       text,
    lower_bound       numeric,
    lower_operator    text,
    upper_bound       numeric,
    upper_operator    text,
    risk_factor_iri   text,
    risk_factor_label text,
    risk_category     text,
    trigger_basis     text NOT NULL,
    external_note     text,
    has_passage       boolean NOT NULL DEFAULT false,
    graph_version     text NOT NULL,
    CONSTRAINT map_risk_rule_basis_ck
        CHECK (trigger_basis IN ('corpus-verbatim', 'external-standard'))
);

COMMENT ON COLUMN diabetes.map_risk_rule.has_passage IS
    '该规则是否挂了可逐字引用的 SourcePassage。false 的规则**不参与 tier 判定** ——'
    '「列不出出处的因子不参与判定」这条硬规矩在这里落地。'
    '它们仍会出现在返回体的 unmapped[] 里，让缺口可见。';

-- ── 未命中记账 ──────────────────────────────────────────────────────
-- 未命中只记账，**绝不猜**。这张表是 explain_gap() 的数据来源。
CREATE TABLE IF NOT EXISTS diabetes.map_unmapped_term (
    term_kind   text NOT NULL,
    term        text NOT NULL,
    context     text,
    hit_count   bigint NOT NULL DEFAULT 0,
    first_seen  timestamptz NOT NULL DEFAULT now(),
    last_seen   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (term_kind, term)
);
