-- 005 · L3 V2 care-chain 规范快照
--
-- 唯一的 RDF 同步来源。真实数据（stg_*）与演示队列（sim_*）在这里汇合，
-- 每一行都带 fact_origin 与 trust_level —— 汇合之后仍然分得清谁是谁。
--
-- 「trust_level 与 fact_origin 是两个正交的维度」这件事值得说清楚：
--   ehr-legacy + Attested    ICD-10 编码、药名（上游真实断言）
--   ehr-legacy + Unverified  检验数值（上游是随机数）
--   demo-cohort + Curated    演示队列的绝大多数
--   demo-cohort + Unverified S23 专门造的"演示里的不可信值"
-- 只有一个维度的话，「真实但不可信」和「虚构但可信」就没法区分，
-- 而这两类恰恰是本项目要讲的核心。

CREATE TABLE IF NOT EXISTS diabetes.core_patient (
    patientid     text PRIMARY KEY,
    sex           text,
    birth_year    integer,
    fact_origin   text NOT NULL,
    demo_scenario text,
    source_table  text NOT NULL,
    source_pk     text NOT NULL,
    projected_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT core_patient_origin_ck
        CHECK (fact_origin IN ('ehr-legacy','derived','demo-cohort'))
);

COMMENT ON COLUMN diabetes.core_patient.birth_year IS
    '可以为 NULL。上游 birthday 有 329/400 落在未来，投影层判定为不可信时直接置 NULL，'
    '而不是算出一个负数年龄传下去 —— 缺失是诚实的，错值不是。';

CREATE TABLE IF NOT EXISTS diabetes.core_encounter (
    encounter_id     text PRIMARY KEY,
    patientid        text NOT NULL,
    encounter_date   date,
    encounter_type   text,
    gestational_week integer,
    fact_origin      text NOT NULL,
    source_table     text NOT NULL,
    source_pk        text NOT NULL
);
CREATE INDEX IF NOT EXISTS core_enc_patient_idx ON diabetes.core_encounter (patientid);

CREATE TABLE IF NOT EXISTS diabetes.core_lab_result (
    lab_result_id text PRIMARY KEY,
    patientid     text NOT NULL,
    encounter_id  text,
    lab_test_iri  text NOT NULL,
    lab_test_code text NOT NULL,
    -- 换算**后**的值与单位，一律是 map_concept_ref.unit_canonical
    result_value  numeric NOT NULL,
    result_unit   text NOT NULL,
    -- 换算**前**的原始值，全程保留以便复核
    source_value  numeric,
    source_unit   text,
    collected_at  timestamp,
    trust_level   text NOT NULL,
    fact_origin   text NOT NULL,
    demo_scenario text,
    source_table  text NOT NULL,
    source_pk     text NOT NULL,
    CONSTRAINT core_lab_trust_ck CHECK (trust_level IN ('Attested','Curated','Unverified')),
    CONSTRAINT core_lab_origin_ck CHECK (fact_origin IN ('ehr-legacy','derived','demo-cohort'))
);
CREATE INDEX IF NOT EXISTS core_lab_patient_idx ON diabetes.core_lab_result (patientid);

COMMENT ON TABLE diabetes.core_lab_result IS
    '进这张表的门槛：必须有可用的概念映射、必须有单位、必须是 quantitative。'
    '任何一条不满足就进 core_observation（保留原样文本）+ 记进 map_unmapped_term，'
    '而不是估一个值塞进来。缺单位的数值不是"差一点可用"，是完全不可用。';
COMMENT ON COLUMN diabetes.core_lab_result.result_unit IS
    'NOT NULL 是刻意的。单位换算只在 ETL 做，进 GraphDB 的 dmo:resultUnit 一律'
    '已是规范单位，SPARQL 里只做 STR(?unit)=STR(?bunit) 的逐字比较，一次换算都不做'
    '（换算系数是 analyte-specific 的，葡萄糖 ×18.0182、肌酐 ÷88.4，写进 SPARQL 必错）。';

CREATE TABLE IF NOT EXISTS diabetes.core_observation (
    observation_id   text PRIMARY KEY,
    patientid        text NOT NULL,
    encounter_id     text,
    observation_type text NOT NULL,
    value_decimal    numeric,
    value_text       text,
    unit_code        text,
    observed_at      timestamp,
    status           text NOT NULL DEFAULT 'Final',
    trust_level      text NOT NULL,
    fact_origin      text NOT NULL,
    demo_scenario    text,
    source_table     text NOT NULL,
    source_pk        text NOT NULL,
    CONSTRAINT core_obs_trust_ck CHECK (trust_level IN ('Attested','Curated','Unverified'))
);
CREATE INDEX IF NOT EXISTS core_obs_patient_idx ON diabetes.core_observation (patientid);

COMMENT ON TABLE diabetes.core_observation IS
    '非检验的临床观察，以及**所有无法作数值判定的检验项**（定性项、缺单位、未映射）。'
    '上游的 resultstateclass（正常/偏高/偏低）也进这里 —— 它是上游的判读，'
    '与本体阈值判定必须物理隔离，绝不进 Assessment。';

CREATE TABLE IF NOT EXISTS diabetes.core_diagnosis (
    diagnosis_id        text PRIMARY KEY,
    patientid           text NOT NULL,
    encounter_id        text,
    diagnosis_kind      text NOT NULL,
    clinical_status     text NOT NULL,
    verification_status text NOT NULL,
    code_system         text,
    external_code       text,
    type_iri            text,
    complication_iri    text,
    diagnosed_date      date,
    caveat              text,
    fact_origin         text NOT NULL,
    demo_scenario       text,
    source_table        text NOT NULL,
    source_pk           text NOT NULL
);
CREATE INDEX IF NOT EXISTS core_dx_patient_idx ON diabetes.core_diagnosis (patientid);

COMMENT ON COLUMN diabetes.core_diagnosis.type_iri IS
    '⚠️ **至多一个**。V2 的 diagnosisType 是 many-to-one，build_tbox 会把它编译成 '
    'owl:FunctionalProperty；一条 Diagnosis 挂两个分型，owl2-rl 会推出两个分型 '
    'owl:sameAs，与 dmo-axioms.ttl 的 AllDisjointClasses 冲突 —— **整个本体不一致'
    '且不报错**。单列而不是数组，就是把这个约束钉死在 schema 上。';

CREATE TABLE IF NOT EXISTS diabetes.core_medication_use (
    medication_use_id text PRIMARY KEY,
    patientid         text NOT NULL,
    encounter_id      text,
    medication_iri    text,
    medication_name   text NOT NULL,
    drug_class_iri    text,
    start_date        date,
    end_date          date,
    status            text NOT NULL,
    regimen_role      text,
    treats_diagnosis  text[] NOT NULL DEFAULT '{}',
    fact_origin       text NOT NULL,
    demo_scenario     text,
    source_table      text NOT NULL,
    source_pk         text NOT NULL
);
CREATE INDEX IF NOT EXISTS core_mu_patient_idx ON diabetes.core_medication_use (patientid);

-- ── RDF 同步状态 ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.sys_rdf_sync_state (
    patientid     text PRIMARY KEY,
    graph_uri     text NOT NULL UNIQUE,
    content_hash  text NOT NULL,
    triple_count  integer NOT NULL DEFAULT 0,
    synced_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE diabetes.sys_rdf_sync_state IS
    '每患者一命名图的同步登记。content_hash 对得上就跳过 PUT —— '
    '「二跑零 PUT」是幂等的可观测证据。'
    '--prune 靠这张表找出「登记过但 SQL 里已不存在」的图，只删这些，'
    '绝不碰 tbox/seed/sources/extract。';
