-- 006 · 单位换算登记表
--
-- ⚠️ 这张表是从 map_lab_term 里**分出来**的，因为那里的键错了。
--
--   map_lab_term 的键是 (上游中文名, 上游参考范围) —— 它回答的是
--   「'血糖' 这个上游名字对应哪个概念」。
--   而单位换算回答的是「LabTest-FPG 这个概念的 mmol/L 怎么变成 mg/dL」，
--   与上游叫它什么毫无关系。
--
--   把两件事塞进一张表的后果实测过：演示队列用本体编码（FPG）记录，
--   上游用中文名（空腹血糖）记录，同一个葡萄糖换算在两条路径上
--   一个查得到一个查不到 —— S11 的单位陷阱场景静默失效，
--   7.8 mmol/L 原样进图，与 mg/dL 的阈值单位对不上，零 Assessment、零报错。
--
-- 现在按 (concept_iri, unit_src) 索引，两条路径共用同一份登记。
-- 「同一个葡萄糖换算，演示和真实数据用的是同一张表」本身也是要演示的事。

CREATE TABLE IF NOT EXISTS diabetes.map_unit_conversion (
    concept_iri  text NOT NULL REFERENCES diabetes.map_concept_ref(iri),
    unit_src     text NOT NULL,
    unit_target  text NOT NULL,
    conv_factor  numeric NOT NULL,
    conv_offset  numeric NOT NULL DEFAULT 0,
    verified_by  text NOT NULL,
    note         text,
    PRIMARY KEY (concept_iri, unit_src),
    -- 恒等换算没有意义，只会掩盖"其实没登记"
    CONSTRAINT map_unit_conv_not_identity CHECK (unit_src <> unit_target)
);

COMMENT ON TABLE diabetes.map_unit_conversion IS
    '换算只在 ETL 做，SPARQL 里一次都不做。系数是 analyte-specific 的'
    '（葡萄糖 ×18.0182 来自分子量 180.16，肌酐 ÷88.4 来自 113.12），'
    '写进 SPARQL 就必须在查询里判断"这是哪个分析物"，判断错一次结论就错。';
COMMENT ON COLUMN diabetes.map_unit_conversion.verified_by IS
    'NOT NULL：换算系数没有"推断"这一档。从参考范围反推出的**单位**是推断，'
    '但一旦决定要换算，系数必须是查得到出处的常数，且必须有人签字。';
