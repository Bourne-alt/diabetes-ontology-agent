"""stg_* + sim_* → core_*（V2 care-chain）。

投影层的全部职责就一句话：**决定每一条上游事实能不能作数值判定，不能就说清为什么。**

分流规则（顺序即优先级）：

    检验结果
      ├─ 术语未映射            → core_observation(value_text) + map_unmapped_term
      ├─ verify_status ≠ verified → core_observation + 计数（candidate 的不生效）
      ├─ value_kind = qualitative → core_observation（尿蛋白「10.4」永不当数值读）
      ├─ 缺单位                 → core_observation + unmapped（P90013 = S12）
      ├─ 数值解析不出           → core_observation
      └─ 全部通过               → core_lab_result（换算已完成）

    每一条被拒的都会留下记录。**沉默地丢弃**是这一层最容易犯也最致命的错误：
    查询返回空集时，分不清是「没有这个患者」「没有这项检验」还是「有但我们判不了」。

上游检验值一律 trust='Unverified'（stg_lis_result.inspectionresult 是随机数），
演示队列按 CSV 的 trust_level 走。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from ..config import Config
from ..terms.units import Conversion, UnitError, convert
from .engine import GuardedConnection, onto_conn

# 上游 birthday 落在这个区间外就判定为不可信，birth_year 置 NULL。
# 上界取"今年"：出生日期在未来是物理上不可能的，不是边界情况。
PLAUSIBLE_BIRTH_YEAR = (1900, 2026)


@dataclass
class Stats:
    lab_ok: int = 0
    lab_rejected: dict[str, int] = field(default_factory=dict)
    observations: int = 0
    diagnoses: int = 0
    dx_unmapped_icd: int = 0
    medications: int = 0
    med_unmapped: int = 0
    patients: int = 0
    encounters: int = 0
    birth_year_dropped: int = 0

    def reject(self, reason: str) -> None:
        self.lab_rejected[reason] = self.lab_rejected.get(reason, 0) + 1


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        return None


def _truncate(conn: GuardedConnection) -> None:
    for t in ("core_lab_result", "core_observation", "core_diagnosis",
              "core_medication_use", "core_encounter", "core_patient"):
        conn.execute(f"TRUNCATE TABLE diabetes.{t}")


# ─────────────────────────── 患者与就诊 ──────────────────────────────


def _project_patients(conn: GuardedConnection, st: Stats) -> None:
    rows = conn.fetchall(
        "SELECT patientid, sexcode, birthday, source_table, source_pk "
        "FROM diabetes.stg_patient_basic"
    )
    payload = []
    for r in rows:
        year = r["birthday"].year if r["birthday"] else None
        if year is not None and not (PLAUSIBLE_BIRTH_YEAR[0] <= year <= PLAUSIBLE_BIRTH_YEAR[1]):
            # 实测 400 人里 329 人出生日期在未来（最晚 2063-09-14）。
            # 传下去会算出负数年龄，风险规则 AGE-35 就会拿它比大小。
            # 置 NULL：缺失是诚实的，错值不是。
            year = None
            st.birth_year_dropped += 1
        payload.append((r["patientid"], r["sexcode"], year, "ehr-legacy", None,
                        r["source_table"], r["source_pk"]))

    for r in conn.fetchall(
        "SELECT patientid, sexcode, birth_year, demo_scenario FROM diabetes.sim_patient"
    ):
        payload.append((r["patientid"], r["sexcode"], r["birth_year"], "demo-cohort",
                        r["demo_scenario"], "diabetes.sim_patient", r["patientid"]))

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO diabetes.core_patient (patientid, sex, birth_year, fact_origin,"
            " demo_scenario, source_table, source_pk) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            payload,
        )
    st.patients = len(payload)


def _project_encounters(conn: GuardedConnection, st: Stats) -> None:
    payload = [
        (f"EHR-{r['source_pk']}", r["patientid"], r["regdate"], r["dept_name"], None,
         "ehr-legacy", r["source_table"], r["source_pk"])
        for r in conn.fetchall(
            "SELECT patientid, regdate, dept_name, source_table, source_pk "
            "FROM diabetes.stg_outpatient_reg"
        )
    ]
    payload += [
        (r["encounter_id"], r["patientid"], r["encounter_date"], r["encounter_type"],
         r["gestational_week"], "demo-cohort", "diabetes.sim_encounter", r["encounter_id"])
        for r in conn.fetchall(
            "SELECT encounter_id, patientid, encounter_date, encounter_type,"
            " gestational_week FROM diabetes.sim_encounter"
        )
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO diabetes.core_encounter (encounter_id, patientid, encounter_date,"
            " encounter_type, gestational_week, fact_origin, source_table, source_pk)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            payload,
        )
    st.encounters = len(payload)


# ─────────────────────────── 检验 ────────────────────────────────────

LAB_SQL = """
SELECT r.source_pk, r.itemname, r.inspectionresult, r.inspectionresultrange,
       r.resultstateclass, r.source_table,
       d.patientid, d.inspectiondate, d.testcode,
       m.concept_iri, m.value_kind, m.verify_status, m.trust_default,
       m.unit_src, m.unit_target, m.conv_factor, m.conv_offset,
       c.code AS lab_test_code
FROM diabetes.stg_lis_result r
JOIN diabetes.stg_lis_detail d ON d.testcode = r.testcode
LEFT JOIN diabetes.map_lab_term m
       ON m.src_name = r.itemname
      AND coalesce(m.src_ref_range,'') = coalesce(r.inspectionresultrange,'')
LEFT JOIN diabetes.map_concept_ref c ON c.iri = m.concept_iri
"""


def _project_ehr_labs(conn: GuardedConnection, st: Stats) -> tuple[list, list]:
    labs, obs = [], []
    for r in conn.fetchall(LAB_SQL):
        rid = f"EHR-LAB-{r['source_pk']}"
        raw = _dec(r["inspectionresult"])

        # 上游的判读（正常/偏高/偏低）永远单独记一条观察。
        # 它是**上游的**结论，与本体阈值判定物理隔离 —— 绝不进 Assessment。
        if r["resultstateclass"]:
            obs.append((f"{rid}-STATE", r["patientid"], None, "Other", None,
                        f"{r['itemname']}：上游判读 {r['resultstateclass']}", None,
                        r["inspectiondate"], "Final", "Unverified", "ehr-legacy", None,
                        r["source_table"], r["source_pk"]))

        reason = None
        if not r["concept_iri"]:
            reason = "术语未映射"
        elif r["verify_status"] != "verified":
            reason = f"映射未核实({r['verify_status']})"
        elif r["value_kind"] != "quantitative":
            reason = f"非数值项({r['value_kind']})"
        elif raw is None:
            reason = "数值解析失败"

        if reason is None:
            conv = _conversion(conn, r["concept_iri"], r["unit_src"] or "")
            try:
                assert raw is not None
                got = convert(raw, r["unit_src"], conv)
            except UnitError as e:
                reason = f"单位问题：{e}"
            else:
                labs.append((rid, r["patientid"], None, r["concept_iri"],
                             r["lab_test_code"] or "?", got.value, got.unit,
                             got.source_value, got.source_unit, r["inspectiondate"],
                             # 上游数值一律 Unverified —— 全库是 0~25 的随机数
                             "Unverified", "ehr-legacy", None,
                             r["source_table"], r["source_pk"]))
                st.lab_ok += 1
                continue

        st.reject(reason)
        obs.append((rid, r["patientid"], None, "Other", None,
                    (f"{r['itemname']} = {r['inspectionresult']} "
                     f"（参考范围 {r['inspectionresultrange'] or '未给'}；"
                     f"未作数值判定：{reason}）"),
                    None, r["inspectiondate"], "Final", "Unverified", "ehr-legacy",
                    None, r["source_table"], r["source_pk"]))
    return labs, obs


def _project_sim_labs(conn: GuardedConnection, st: Stats) -> tuple[list, list]:
    labs, obs = [], []
    rows = conn.fetchall(
        """
        SELECT s.*, c.iri AS concept_iri
        FROM diabetes.sim_lab_result s
        LEFT JOIN diabetes.map_concept_ref c
               ON c.concept_kind = 'LabTest' AND c.code = s.lab_test_code
        """
    )
    for r in rows:
        raw = _dec(r["result_value"])
        reason = None
        if not r["concept_iri"]:
            reason = f"检验编码 {r['lab_test_code']} 在本体里找不到"
        elif raw is None:
            reason = "数值缺失"
        elif not r["result_unit"]:
            reason = "缺单位"

        if reason is None:
            # 演示队列直接给规范单位或 mmol/L。换算规则同样查 map_lab_term，
            # 查不到就按"原样通过"处理 —— 但单位必须已经是本体的规范单位。
            conv = _conversion(conn, r["concept_iri"], r["result_unit"])
            try:
                assert raw is not None
                got = convert(raw, r["result_unit"], conv)
            except UnitError as e:
                reason = str(e)
            else:
                labs.append((r["lab_result_id"], r["patientid"], r["encounter_id"],
                             r["concept_iri"], r["lab_test_code"], got.value, got.unit,
                             got.source_value, got.source_unit, r["collected_at"],
                             r["trust_level"], "demo-cohort", r["demo_scenario"],
                             "diabetes.sim_lab_result", r["lab_result_id"]))
                st.lab_ok += 1
                continue

        st.reject(reason)
        obs.append((r["lab_result_id"], r["patientid"], r["encounter_id"], "Other", None,
                    (f"{r['lab_test_code']} = {r['result_value']} "
                     f"{r['result_unit'] or '(无单位)'}（未作数值判定：{reason}）"),
                    None, r["collected_at"], "Final", r["trust_level"], "demo-cohort",
                    r["demo_scenario"], "diabetes.sim_lab_result", r["lab_result_id"]))
    return labs, obs


_CONV_CACHE: dict[tuple[str, str], Conversion] = {}


def _conversion(conn: GuardedConnection, concept_iri: str, unit: str) -> Conversion:
    """按 (概念, 原始单位) 查换算登记表。**真实数据与演示队列共用这一张表。**

    键是概念 IRI 而不是上游中文名：换算是分析物的物理性质，与上游叫它什么无关。
    早先把换算挂在 map_lab_term（键是上游中文名）上，结果演示队列用本体编码
    记录、上游用中文名记录，同一个葡萄糖换算一条路径查得到、另一条查不到 ——
    S11 的单位陷阱静默失效，7.8 mmol/L 原样进图，与 mg/dL 的阈值单位对不上，
    零 Assessment 且零报错。
    """
    key = (concept_iri, unit)
    if key in _CONV_CACHE:
        return _CONV_CACHE[key]
    row = conn.fetchone(
        "SELECT unit_src, unit_target, conv_factor, conv_offset "
        "FROM diabetes.map_unit_conversion WHERE concept_iri = %s AND unit_src = %s",
        (concept_iri, unit),
    )
    conv = (
        Conversion(row["unit_src"], row["unit_target"], _dec(row["conv_factor"]),
                   _dec(row["conv_offset"]) or Decimal(0))
        if row else Conversion(None, None, None)   # 没登记就不换算，原样通过
    )
    _CONV_CACHE[key] = conv
    return conv


# ─────────────────────────── 诊断与用药 ──────────────────────────────


def _project_diagnoses(conn: GuardedConnection, st: Stats) -> None:
    payload = []
    for r in conn.fetchall(
        """
        SELECT d.source_pk, d.patientid, d.icd10code, d.icd10name, d.createdtime,
               d.source_table, m.concept_iri, m.concept_kind, m.verify_status
        FROM diabetes.stg_diagnose d
        LEFT JOIN diabetes.map_icd10 m ON m.icd10code = d.icd10code
        """
    ):
        kind = {"DiabetesType": "Diabetes", "Complication": "Complication",
                "Comorbidity": "Comorbidity"}.get(r["concept_kind"] or "")
        if kind is None:
            # Unrelated 或未映射：不进 core_diagnosis。这不是丢弃 ——
            # 未映射的已由 scan_unmapped 记账，Unrelated 是明确的人工判断。
            if not r["concept_kind"]:
                st.dx_unmapped_icd += 1
            continue
        payload.append((
            f"EHR-DX-{r['source_pk']}", r["patientid"], None, kind, "Active",
            # ICD-10 编码是上游的真实断言，按 Confirmed 处理。
            # 但它只说明"上游记了这个码"，不代表本体阈值也支持 —— 两条证据链分开。
            "Confirmed", "ICD-10", r["icd10code"],
            r["concept_iri"] if kind == "Diabetes" else None,
            r["concept_iri"] if kind == "Complication" else None,
            None, None, "ehr-legacy", None, r["source_table"], r["source_pk"],
        ))
    for r in conn.fetchall("SELECT * FROM diabetes.sim_diagnosis"):
        payload.append((
            r["diagnosis_id"], r["patientid"], r["encounter_id"], r["diagnosis_kind"],
            r["clinical_status"], r["verification_status"],
            "ICD-10" if r["icd10code"] else None, r["icd10code"],
            r["type_iri"], r["complication_iri"], r["diagnosed_date"], r.get("caveat"),
            "demo-cohort", r["demo_scenario"], "diabetes.sim_diagnosis", r["diagnosis_id"],
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO diabetes.core_diagnosis (diagnosis_id, patientid, encounter_id,"
            " diagnosis_kind, clinical_status, verification_status, code_system,"
            " external_code, type_iri, complication_iri, diagnosed_date, caveat,"
            " fact_origin, demo_scenario, source_table, source_pk)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            payload,
        )
    st.diagnoses = len(payload)


def _project_medications(conn: GuardedConnection, st: Stats) -> None:
    payload = []
    for r in conn.fetchall(
        """
        SELECT o.source_pk, o.patientid, o.termname, o.modate, o.source_table,
               m.medication_iri, m.drug_class_iri, m.verify_status
        FROM diabetes.stg_op_order o
        LEFT JOIN diabetes.map_drug_term m ON m.src_name = o.termname
        """
    ):
        if not r["medication_iri"]:
            # 非降糖药（阿司匹林等）与未映射药名都落这里。前者是明确判断，
            # 后者已由 scan_unmapped 记账 —— 都不进 core，也都不假装不存在。
            st.med_unmapped += 1
            continue
        payload.append((
            f"EHR-MU-{r['source_pk']}", r["patientid"], None, r["medication_iri"],
            r["termname"], r["drug_class_iri"], None, None, "Active", None, [],
            "ehr-legacy", None, r["source_table"], r["source_pk"],
        ))
    for r in conn.fetchall(
        """
        SELECT s.*, m.medication_iri, m.drug_class_iri
        FROM diabetes.sim_medication_use s
        LEFT JOIN diabetes.map_drug_term m ON m.src_name = s.medication_name
        """
    ):
        if not r["medication_iri"]:
            st.med_unmapped += 1
            continue
        treats = [t for t in (r["treats_diagnosis"] or "").split(";") if t]
        payload.append((
            r["medication_use_id"], r["patientid"], None, r["medication_iri"],
            r["medication_name"], r["drug_class_iri"], r["start_date"], r["end_date"],
            r["status"], r["regimen_role"], treats, "demo-cohort", r["demo_scenario"],
            "diabetes.sim_medication_use", r["medication_use_id"],
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO diabetes.core_medication_use (medication_use_id, patientid,"
            " encounter_id, medication_iri, medication_name, drug_class_iri, start_date,"
            " end_date, status, regimen_role, treats_diagnosis, fact_origin,"
            " demo_scenario, source_table, source_pk)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            payload,
        )
    st.medications = len(payload)


def _project_sim_observations(conn: GuardedConnection) -> list:
    return [
        (r["observation_id"], r["patientid"], r["encounter_id"], r["observation_type"],
         r["value_decimal"], r["value_text"], r["unit_code"], r["observed_at"], "Final",
         r["trust_level"], "demo-cohort", r["demo_scenario"],
         "diabetes.sim_observation", r["observation_id"])
        for r in conn.fetchall("SELECT * FROM diabetes.sim_observation")
    ]


# ─────────────────────────── 入口 ────────────────────────────────────


def run(cfg: Config) -> int:
    from . import baseline

    if baseline.check(cfg, quiet=True) != 0:
        baseline.check(cfg)
        print("\n  上游已变，拒绝投影 —— 拿着过期快照往下算，后面每一层都是错的。")
        return 1

    st = Stats()
    _CONV_CACHE.clear()
    with onto_conn(cfg) as conn:
        _truncate(conn)
        _project_patients(conn, st)
        _project_encounters(conn, st)

        ehr_labs, ehr_obs = _project_ehr_labs(conn, st)
        sim_labs, sim_obs = _project_sim_labs(conn, st)
        obs = ehr_obs + sim_obs + _project_sim_observations(conn)

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO diabetes.core_lab_result (lab_result_id, patientid,"
                " encounter_id, lab_test_iri, lab_test_code, result_value, result_unit,"
                " source_value, source_unit, collected_at, trust_level, fact_origin,"
                " demo_scenario, source_table, source_pk)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                ehr_labs + sim_labs,
            )
            cur.executemany(
                "INSERT INTO diabetes.core_observation (observation_id, patientid,"
                " encounter_id, observation_type, value_decimal, value_text, unit_code,"
                " observed_at, status, trust_level, fact_origin, demo_scenario,"
                " source_table, source_pk) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                obs,
            )
        st.observations = len(obs)

        _project_diagnoses(conn, st)
        _project_medications(conn, st)
        conn.commit()

    print("✓ 投影完成")
    print(f"    患者          {st.patients}"
          f"（其中 {st.birth_year_dropped} 人出生年份不可信，已置 NULL）")
    print(f"    就诊          {st.encounters}")
    print(f"    检验（可判定） {st.lab_ok}")
    print(f"    观察          {st.observations}")
    print(f"    诊断          {st.diagnoses}（{st.dx_unmapped_icd} 条 ICD-10 未映射，已记账）")
    print(f"    用药          {st.medications}（{st.med_unmapped} 条药名非降糖或未映射）")
    if st.lab_rejected:
        print("\n  检验被拒进 core_lab_result 的原因分布（全部已进 core_observation）：")
        for reason, n in sorted(st.lab_rejected.items(), key=lambda kv: -kv[1]):
            print(f"      {n:>5}  {reason}")
        print("  ↑ 这些不是丢失的数据，是**明确判定为不可作数值判定**的数据。")
    return 0
