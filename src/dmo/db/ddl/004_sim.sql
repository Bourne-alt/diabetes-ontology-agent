-- 004 · L1 演示队列 P90001–P90030
--
-- ⚠️ 与 plan 的一处**偏离**，理由必须写清楚
--   plan 里写的是「sim_* 结构与 stg_* 对应表一致」。实际做成了 **core 形状**。
--
--   因为上游那套结构表达不了演示要验证的东西：
--     · cdr_lis_result 没有单位列          ⟹ S11 单位陷阱造不出来
--     · 没有任何「空腹/餐后」标注          ⟹ FPG 诊断切点用不上
--     · 没有 ClinicalObservation 这类表    ⟹ BMI / 妊娠状态 / 吸烟无处安放
--     · 每个患者恰好一条诊断、一次检验     ⟹ S03 复测确诊、S14 纵向随访造不出来
--
--   硬要对齐上游结构，等于让演示队列继承上游的表达贫困，
--   那 18 个场景里至少 8 个直接做不了。
--
--   代价是 projection.py 要处理两种入参形状。这个代价是值得的，而且它本身
--   就是演示的一部分：**真实 EHR 记不下的东西，本体也判不了** —— Q4 讲的就是这个。
--
-- 每张表都带 demo_scenario。任何一条演示事实，从 SQL 到 RDF 到 API 返回体，
-- 全程带着 factOrigin='demo-cohort'，不可能被误当成真实病历。

CREATE TABLE IF NOT EXISTS diabetes.sim_patient (
    patientid     text PRIMARY KEY,
    sexcode       text,
    birth_year    integer,
    demo_scenario text NOT NULL,
    demo_note     text,
    CONSTRAINT sim_patient_id_range CHECK (patientid ~ '^P9[0-9]{4}$')
);

COMMENT ON CONSTRAINT sim_patient_id_range ON diabetes.sim_patient IS
    '演示患者号段固定在 P90001–P99999，与真实的 P00001–P00400 格式相同但不重叠。'
    '格式相同是为了证明管线不靠 ID 形状区分真假；号段隔离是为了不可能撞号。';

CREATE TABLE IF NOT EXISTS diabetes.sim_encounter (
    encounter_id     text PRIMARY KEY,
    patientid        text NOT NULL REFERENCES diabetes.sim_patient(patientid),
    encounter_date   date NOT NULL,
    encounter_type   text,
    gestational_week integer,
    demo_scenario    text NOT NULL
);
CREATE INDEX IF NOT EXISTS sim_encounter_patient_idx ON diabetes.sim_encounter (patientid);

CREATE TABLE IF NOT EXISTS diabetes.sim_lab_result (
    lab_result_id  text PRIMARY KEY,
    patientid      text NOT NULL REFERENCES diabetes.sim_patient(patientid),
    encounter_id   text REFERENCES diabetes.sim_encounter(encounter_id),
    lab_test_code  text NOT NULL,
    result_value   numeric,
    result_unit    text,
    collected_at   timestamp NOT NULL,
    trust_level    text NOT NULL DEFAULT 'Curated',
    demo_scenario  text NOT NULL,
    demo_note      text,
    CONSTRAINT sim_lab_trust_ck CHECK (trust_level IN ('Attested','Curated','Unverified'))
);
CREATE INDEX IF NOT EXISTS sim_lab_patient_idx ON diabetes.sim_lab_result (patientid);

COMMENT ON COLUMN diabetes.sim_lab_result.result_unit IS
    '可以为 NULL —— S12 就是专门造的「缺单位」场景，必须能表达。'
    '投影层遇到 NULL 单位一律拒绝进 core_lab_result。';
COMMENT ON COLUMN diabetes.sim_lab_result.lab_test_code IS
    '本体的 dmo:labTestCode（A1C / FPG / GCT1H / UACR / GLU …）。'
    '演示队列直接用编码而不是中文名：它绕过术语映射层，这是刻意的 ——'
    '演示要验证的是阈值判定，不是映射；映射由真实数据那条路径验证。';

CREATE TABLE IF NOT EXISTS diabetes.sim_diagnosis (
    diagnosis_id        text PRIMARY KEY,
    patientid           text NOT NULL REFERENCES diabetes.sim_patient(patientid),
    encounter_id        text REFERENCES diabetes.sim_encounter(encounter_id),
    diagnosis_kind      text NOT NULL,
    clinical_status     text NOT NULL DEFAULT 'Active',
    verification_status text NOT NULL DEFAULT 'Confirmed',
    icd10code           text,
    type_iri            text,
    complication_iri    text,
    diagnosed_date      date,
    demo_scenario       text NOT NULL,
    CONSTRAINT sim_dx_kind_ck CHECK (diagnosis_kind IN
        ('Diabetes','Prediabetes','Complication','Comorbidity','AcuteEvent'))
);
CREATE INDEX IF NOT EXISTS sim_dx_patient_idx ON diabetes.sim_diagnosis (patientid);

CREATE TABLE IF NOT EXISTS diabetes.sim_medication_use (
    medication_use_id text PRIMARY KEY,
    patientid         text NOT NULL REFERENCES diabetes.sim_patient(patientid),
    medication_name   text NOT NULL,
    start_date        date,
    end_date          date,
    status            text NOT NULL DEFAULT 'Active',
    regimen_role      text,
    treats_diagnosis  text,
    demo_scenario     text NOT NULL,
    CONSTRAINT sim_mu_status_ck CHECK (status IN
        ('Active','Completed','Stopped','OnHold','Unknown'))
);
CREATE INDEX IF NOT EXISTS sim_mu_patient_idx ON diabetes.sim_medication_use (patientid);

COMMENT ON TABLE diabetes.sim_medication_use IS
    '⚠️ **没有任何剂量字段**，schema 层面堵死越界输出。'
    'regimen_role 只记「基础胰岛素/口服降糖」这类角色，不含数字。';

CREATE TABLE IF NOT EXISTS diabetes.sim_observation (
    observation_id   text PRIMARY KEY,
    patientid        text NOT NULL REFERENCES diabetes.sim_patient(patientid),
    encounter_id     text REFERENCES diabetes.sim_encounter(encounter_id),
    observation_type text NOT NULL,
    value_decimal    numeric,
    value_text       text,
    unit_code        text,
    observed_at      timestamp NOT NULL,
    trust_level      text NOT NULL DEFAULT 'Curated',
    demo_scenario    text NOT NULL
);
CREATE INDEX IF NOT EXISTS sim_obs_patient_idx ON diabetes.sim_observation (patientid);

COMMENT ON COLUMN diabetes.sim_observation.observation_type IS
    'BMI / SmokingStatus / PregnancyStatus / GestationalAge / SystolicBP / '
    'FamilyHistory / PhysicalActivityPerWeek。后两个不在 V2 的 observationType 枚举里，'
    '投影时映到 Other + value_text —— 风险规则按 observedKind 匹配，不依赖枚举。';
