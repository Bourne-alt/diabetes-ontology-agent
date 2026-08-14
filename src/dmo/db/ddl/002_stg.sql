-- 002 · L0 上游快照
--
-- 列名列型与 hospital_zd.patient_analysis 对应表**逐字一致**，另加四列溯源字段。
-- 逐字一致是刻意的：任何「顺手规范一下」的改名都会让「回查原始那一行」这件事
-- 需要一张对照表，而对照表迟早会和现实脱节。
--
-- ⚠️ 姓名与身份证号**不在这里**
--   patient_basic_info 的 name / idenno / hometel / linkmanname / linkmantel /
--   monthername / home 一列都不拉。脱敏做在**入口**而不是出口：
--   拉进来再在输出层过滤，等于赌每一个未来的查询都记得过滤。
--   不拉进来，就没有任何查询能泄露它们。
--   患者身份靠 patientid 假名维系，够用。

-- ── 患者人口学 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.stg_patient_basic (
    patientid    varchar(255) NOT NULL,
    sexcode      varchar(255),
    birthday     timestamp,
    nationcode   varchar(255),
    vipflag      varchar(255),
    mari         varchar(255),
    relacode     varchar(255),
    istreatment  varchar(255),
    lregdate     timestamp,
    lihosdate    timestamp,
    louthosdate  timestamp,
    councode     varchar(255),
    province     varchar(255),
    city         varchar(255),
    area         varchar(255),
    profcode     varchar(255),
    pactcode     varchar(255),
    pactname     varchar(255),
    paykindcode  varchar(255),
    -- 溯源
    source_table text        NOT NULL DEFAULT 'patient_analysis.patient_basic_info',
    source_pk    text        NOT NULL,
    pulled_at    timestamptz NOT NULL DEFAULT now(),
    pull_batch   text        NOT NULL,
    PRIMARY KEY (patientid)
);

COMMENT ON COLUMN diabetes.stg_patient_basic.birthday IS
    '⚠️ 上游此列不可信：实测取值 2020-02-24 ~ 2063-09-14，400 人里 329 人出生日期在未来。'
    '任何按年龄的判定（如 RiskRule AGE-35）对这批数据都必须拒绝出结论，'
    '而不是算出一个负数年龄然后当真。';

-- ── 诊断 ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.stg_diagnose (
    patientid       varchar(255) NOT NULL,
    clinicno        varchar(255),
    diseaseid       varchar(255),
    diseasetype     varchar(255),
    diseasetypecode varchar(255),
    icd10code       varchar(255),
    icd10name       varchar(255),
    createdtime     varchar(255),
    source_table    text        NOT NULL DEFAULT 'patient_analysis.diagnose_query',
    source_pk       text        NOT NULL,
    pulled_at       timestamptz NOT NULL DEFAULT now(),
    pull_batch      text        NOT NULL,
    PRIMARY KEY (source_pk)
);
CREATE INDEX IF NOT EXISTS stg_diagnose_patient_idx ON diabetes.stg_diagnose (patientid);
CREATE INDEX IF NOT EXISTS stg_diagnose_icd_idx     ON diabetes.stg_diagnose (icd10code);

-- ── 检验主表（大项）─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.stg_lis_detail (
    patientid      varchar NOT NULL,
    visitedid      varchar,
    itemcode       varchar,
    itemname       varchar,
    ordsn          varchar,
    sampletype     varchar,
    specimename    varchar,
    inspectiondate timestamp,
    testcode       varchar,
    source_table   text        NOT NULL DEFAULT 'patient_analysis.cdr_lis_detail',
    source_pk      text        NOT NULL,
    pulled_at      timestamptz NOT NULL DEFAULT now(),
    pull_batch     text        NOT NULL,
    PRIMARY KEY (source_pk)
);
CREATE INDEX IF NOT EXISTS stg_lis_detail_patient_idx ON diabetes.stg_lis_detail (patientid);
CREATE INDEX IF NOT EXISTS stg_lis_detail_test_idx    ON diabetes.stg_lis_detail (testcode);

COMMENT ON COLUMN diabetes.stg_lis_detail.itemname IS
    '⚠️ 大项名，**纯噪声，一律不做术语映射**。实测 itemname=''糖化血红蛋白'' 的检验单下面'
    '挂的子项是 AST / 尿蛋白 / 血小板 / 尿素氮，主子表语义错位。'
    '映射它等于主动制造错误 —— 唯一可信的 analyte 来源是 stg_lis_result.itemname。';

-- ── 检验结果（子项）─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.stg_lis_result (
    testcode              varchar,
    itemcode              varchar,
    itemname              varchar,
    ordsn                 varchar,
    inspectionresult      varchar,
    inspectionresultrange varchar,
    resultstateclass      varchar,
    source_table          text        NOT NULL DEFAULT 'patient_analysis.cdr_lis_result',
    source_pk             text        NOT NULL,
    pulled_at             timestamptz NOT NULL DEFAULT now(),
    pull_batch            text        NOT NULL,
    PRIMARY KEY (source_pk)
);
CREATE INDEX IF NOT EXISTS stg_lis_result_test_idx ON diabetes.stg_lis_result (testcode);
CREATE INDEX IF NOT EXISTS stg_lis_result_name_idx ON diabetes.stg_lis_result (itemname);

COMMENT ON COLUMN diabetes.stg_lis_result.inspectionresult IS
    '⚠️ 数值不可信：全库取值集中在 0~25，与参考范围毫无关系'
    '（血小板 15.3 而参考范围 100-300，却标 resultstateclass=正常）。'
    '投影进 core_lab_result 时强制 trust_level=''Unverified''，默认不参与阈值判定。';
COMMENT ON COLUMN diabetes.stg_lis_result.inspectionresultrange IS
    '参考范围。原表**没有单位列**，这是推断单位的唯一线索'
    '（血糖 3.9-6.1 ⟹ mmol/L）。推断结果必须人工在 map_lab_term 里 verified 才生效。';
COMMENT ON COLUMN diabetes.stg_lis_result.resultstateclass IS
    '上游的判读（正常/偏高/偏低/异常）。只进 ClinicalObservation，**绝不进 Assessment** ——'
    '上游判读与本体阈值判定必须物理隔离，否则分不清结论是谁下的。';

-- ── 门诊医嘱（药品）─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.stg_op_order (
    patientid     varchar(255) NOT NULL,
    clinicno      varchar(255),
    canceldate    varchar(255),
    termclass     varchar(255),
    termclassname varchar(255),
    termid        varchar(255),
    termname      varchar(255),
    costref       numeric,
    modate        varchar(255),
    combono       varchar(255),
    source_table  text        NOT NULL DEFAULT 'patient_analysis.op_order_query',
    source_pk     text        NOT NULL,
    pulled_at     timestamptz NOT NULL DEFAULT now(),
    pull_batch    text        NOT NULL,
    PRIMARY KEY (source_pk)
);
CREATE INDEX IF NOT EXISTS stg_op_order_patient_idx ON diabetes.stg_op_order (patientid);
CREATE INDEX IF NOT EXISTS stg_op_order_term_idx    ON diabetes.stg_op_order (termname);

COMMENT ON COLUMN diabetes.stg_op_order.termname IS
    '药名。termclass 全库只有 ''01 药品'' 一种。实测全库唯一的降糖药是二甲双胍（33 条），'
    '其余是阿司匹林 / 氯雷他定 / 辛伐他汀 等非降糖药。';

-- ── 门诊挂号（就诊锚点）─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diabetes.stg_outpatient_reg (
    patientid       varchar(255) NOT NULL,
    clinicno        varchar(255),
    add_flag        varchar(255),
    bgn_time        timestamp,
    book_type       varchar(255),
    branch_no       varchar(255),
    cancel_date     timestamp,
    dept_code       varchar(255),
    dept_name       varchar(100),
    dept_address    varchar(255),
    is_emergency    varchar(255),
    own_cost        numeric,
    pay_cost        numeric,
    pub_cost        numeric,
    reg_level_code  varchar(10),
    reg_level_name  varchar(50),
    regdate         timestamp,
    source_table    text        NOT NULL DEFAULT 'patient_analysis.patient_finoprreglist',
    source_pk       text        NOT NULL,
    pulled_at       timestamptz NOT NULL DEFAULT now(),
    pull_batch      text        NOT NULL,
    PRIMARY KEY (source_pk)
);
CREATE INDEX IF NOT EXISTS stg_outpatient_reg_patient_idx ON diabetes.stg_outpatient_reg (patientid);
