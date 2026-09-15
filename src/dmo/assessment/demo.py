"""Owned, synthetic treatment-assessment scenarios and scoped seed loading."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from psycopg import sql
from rdflib import Graph, Literal, Namespace

from ..db.engine import onto_conn

PREFIX = "TA-DEMO-"
SCENARIOS = [
    {"pid": "P91001", "title": "基础评估与数值推演", "focus": "近期 A1C、FPG 与既有用药；可单独执行数值推演（机器学习模型）。", "expected": "检查区间结论、原文出处与模型计算步骤", "labs": [("A1C", 7.8, "percent"), ("FPG", 162.1638, "mg-per-dL")]},
    {"pid": "P91002", "title": "肾脏条件与药物注意事项", "focus": "已确认活动性 CKD、UACR 与肾功能记录。", "expected": "肾脏阈值与条件性药物注意事项（取决于本地原文覆盖）", "condition": "CKD", "labs": [("A1C", 8.1, "percent"), ("UACR", 85, "mg-per-g"), ("EGFR", 38, "mL-per-min")]},
    {"pid": "P91003", "title": "多项用药与多维资料", "focus": "两项既有药物及糖代谢、肝脏、心血管、生活方式资料。", "expected": "六维覆盖差异、联合作用尚未建模", "meds": ["metformin", "empagliflozin"], "labs": [("A1C", 7.3, "percent"), ("ALT", 45, "U/L"), ("CHOL", 210, "mg-per-dL")]},
    {"pid": "P91004", "title": "同一时刻结果冲突", "focus": "同一采集时间的两条 A1C 数值不同。", "expected": "resolve_conflicting_measurements，暂停阈值判断", "labs": [("A1C", 5.8, "percent"), ("A1C", 8.2, "percent")]},
    {"pid": "P91005", "title": "不可信检验值", "focus": "保留未核验的 A1C 值，不提升为可信测量。", "expected": "verified_value 缺口，无该数值的阈值结论", "trust": "Unverified", "labs": [("A1C", 9.0, "percent")]},
    {"pid": "P91006", "title": "缺少单位", "focus": "检验只保留在临床观察中，不生成标准化检验结果。", "expected": "缺单位原始记录与维度资料缺口", "labs": []},
    {"pid": "P91007", "title": "资料超过评估窗口", "focus": "130 天前的检查只能列入历史。", "expected": "recent_record 缺口，无近期测量结论", "age_days": 130, "labs": [("A1C", 7.6, "percent")]},
    {"pid": "P91008", "title": "暂停用药与措施缺失", "focus": "OnHold 记录不作为继续用药的依据。", "expected": "current_intervention 缺口，措施列表为空", "med_status": "OnHold", "labs": [("A1C", 6.1, "percent")]},
]


def catalog():
    return [{k: s[k] for k in ("pid", "title", "focus", "expected")} for s in SCENARIOS]


def rows_for_scenario(s, reference_date):
    pid = s["pid"]
    scenario = PREFIX + pid
    at = datetime.combine(reference_date, datetime.min.time()) + timedelta(hours=9)
    at -= timedelta(days=s.get("age_days", 1))
    recent = datetime.combine(reference_date, datetime.min.time()) - timedelta(days=1)
    origin = {"fact_origin": "demo-cohort", "demo_scenario": scenario}
    def provenance(table, key):
        return {**origin, "source_table": "diabetes." + table, "source_pk": key}

    tables = {name: [] for name in ("sim_patient", "core_patient", "sim_encounter", "core_encounter",
                                   "sim_lab_result", "core_lab_result", "sim_observation", "core_observation",
                                   "sim_diagnosis", "core_diagnosis", "sim_medication_use", "core_medication_use")}
    tables["sim_patient"].append({"patientid": pid, "sexcode": "Female", "birth_year": 1976,
                                   "demo_scenario": scenario, "demo_note": s["title"] + "；完全合成数据"})
    tables["core_patient"].append({"patientid": pid, "sex": "Female", "birth_year": 1976,
                                    **provenance("sim_patient", pid)})
    encounter = pid + "-ENC"
    tables["sim_encounter"].append({"encounter_id": encounter, "patientid": pid,
                                     "encounter_date": at.date(), "encounter_type": "Outpatient", "demo_scenario": scenario})
    tables["core_encounter"].append({**tables["sim_encounter"][0], **provenance("sim_encounter", encounter)})
    tables["core_encounter"][0].pop("demo_scenario")
    graph = Graph().parse(Path(__file__).resolve().parents[3] / "ontology/src/dmo-threshold-seed.ttl")
    dmo = Namespace("https://example.org/dmo#")
    for i, (metric, value, unit) in enumerate(s["labs"]):
        key = f"{pid}-LAB-{i}"
        iri = graph.value(predicate=dmo.labTestCode, object=Literal(metric))
        if iri is None:
            raise ValueError("Unknown demo metric: " + metric)
        row = {"lab_result_id": key, "patientid": pid, "encounter_id": encounter,
               "lab_test_code": metric, "result_value": value, "result_unit": unit,
               "collected_at": at, "trust_level": s.get("trust", "Curated"), "demo_scenario": scenario}
        tables["sim_lab_result"].append(row)
        tables["core_lab_result"].append({**row, "lab_test_iri": str(iri),
                                            "source_value": value, "source_unit": unit,
                                            **provenance("sim_lab_result", key)})
    observations = [("PregnancyStatus", None, "NotPregnant", None, at - timedelta(hours=1))]
    if pid == "P91003":
        observations += [("BMI", 28, "合成生活方式记录", "kg-per-m2", recent),
                         ("SmokingStatus", None, "Former", None, recent)]
    if pid == "P91006":
        observations += [("Other", None, "A1C 原始值 8.4，单位缺失，未作数值判定", None, recent)]
    for i, (kind, value, text, unit, occurred) in enumerate(observations):
        key = f"{pid}-OBS-{i}"
        row = {"observation_id": key, "patientid": pid, "encounter_id": encounter,
               "observation_type": kind, "value_decimal": value, "value_text": text,
               "unit_code": unit, "observed_at": occurred, "trust_level": "Curated", "demo_scenario": scenario}
        tables["sim_observation"].append(row)
        tables["core_observation"].append({**row, "status": "Final", **provenance("sim_observation", key)})
    if s.get("condition"):
        key = pid + "-DX"
        row = {"diagnosis_id": key, "patientid": pid, "encounter_id": encounter,
               "diagnosis_kind": "Complication", "clinical_status": "Active", "verification_status": "Confirmed",
               "complication_iri": "https://example.org/dmo/id/" + s["condition"],
               "diagnosed_date": recent.date(), "demo_scenario": scenario}
        tables["sim_diagnosis"].append(row)
        tables["core_diagnosis"].append({**row, **provenance("sim_diagnosis", key)})
    for i, code in enumerate(s.get("meds", ["metformin"])):
        key = f"{pid}-MED-{i}"
        names = {"metformin": "二甲双胍", "empagliflozin": "恩格列净"}
        row = {"medication_use_id": key, "patientid": pid, "medication_name": names[code],
               "start_date": recent.date(), "status": s.get("med_status", "Active"), "demo_scenario": scenario}
        tables["sim_medication_use"].append(row)
        tables["core_medication_use"].append({**row, "medication_iri": "https://example.org/dmo/id/medication/" + code,
            "drug_class_iri": "https://example.org/dmo/id/DrugClass-" + ("Biguanide" if code == "metformin" else "SGLT2i"),
            **provenance("sim_medication_use", key)})
    return tables


def seed(cfg, reference_date=None):
    """One atomic replacement of our eight owned demo patients, never a full projection."""
    reference_date = reference_date or datetime.now(ZoneInfo("Asia/Taipei")).date()
    batches = [rows_for_scenario(s, reference_date) for s in SCENARIOS]
    counts = {}
    with onto_conn(cfg) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(9100191008)")
        for s in SCENARIOS:
            for table in ("core_patient", "sim_patient"):
                existing = conn.fetchone(f"SELECT * FROM diabetes.{table} WHERE patientid = %s", (s["pid"],))
                if existing and (existing.get("demo_scenario") != PREFIX + s["pid"]
                                 or (table == "core_patient" and existing["fact_origin"] != "demo-cohort")):
                    raise ValueError("Refusing to overwrite an unowned patient: " + s["pid"])
        for batch, s in zip(batches, SCENARIOS, strict=True):
            # Reverse dependency order, only these explicitly owned patient IDs.
            for table in reversed(list(batch)):
                conn.execute(f"DELETE FROM diabetes.{table} WHERE patientid = %s", (s["pid"],))
            for table, rows in batch.items():
                for row in rows:
                    conn.execute(sql.SQL("INSERT INTO diabetes.{} ({}) VALUES ({})").format(
                        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, row)),
                        sql.SQL(",").join(sql.Placeholder() for _ in row)), tuple(row.values()))
                counts[table] = counts.get(table, 0) + len(rows)
        conn.commit()
    return {"reference_date": str(reference_date), "patients": catalog(), "rows": counts}
