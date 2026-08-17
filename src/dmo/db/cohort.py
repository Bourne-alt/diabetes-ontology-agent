"""演示队列的幂等装载：seed/cohort_*.csv → diabetes.sim_*

CSV 而不是 SQL INSERT 脚本：这批数据是**要被人反复读和改**的（每一行都对应一个
验证点），CSV 在 code review 里能看出「哪个值改了」，SQL 语句块看不出来。

幂等靠 UPSERT + 删除 CSV 里已不存在的行：跑两遍行数必须不变，
且从 CSV 里删掉一行、重跑，库里也要跟着少一行 —— 否则 CSV 就不是真相来源了。
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..config import Config
from .engine import onto_conn

SEED_DIR = Path(__file__).parent / "seed"

# (CSV 文件, 目标表, 主键列, 全部列)。顺序即装载顺序 —— 外键决定了它。
SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("cohort_patient.csv", "sim_patient", "patientid",
     ("patientid", "sexcode", "birth_year", "demo_scenario", "demo_note")),
    ("cohort_encounter.csv", "sim_encounter", "encounter_id",
     ("encounter_id", "patientid", "encounter_date", "encounter_type",
      "gestational_week", "demo_scenario")),
    ("cohort_lab_result.csv", "sim_lab_result", "lab_result_id",
     ("lab_result_id", "patientid", "encounter_id", "lab_test_code", "result_value",
      "result_unit", "collected_at", "trust_level", "demo_scenario", "demo_note")),
    ("cohort_diagnosis.csv", "sim_diagnosis", "diagnosis_id",
     ("diagnosis_id", "patientid", "encounter_id", "diagnosis_kind", "clinical_status",
      "verification_status", "icd10code", "type_iri", "complication_iri",
      "diagnosed_date", "demo_scenario", "caveat")),
    ("cohort_medication_use.csv", "sim_medication_use", "medication_use_id",
     ("medication_use_id", "patientid", "medication_name", "start_date", "end_date",
      "status", "regimen_role", "treats_diagnosis", "demo_scenario")),
    ("cohort_observation.csv", "sim_observation", "observation_id",
     ("observation_id", "patientid", "encounter_id", "observation_type",
      "value_decimal", "value_text", "unit_code", "observed_at", "trust_level",
      "demo_scenario")),
)


def _read(name: str, cols: tuple[str, ...]) -> list[tuple]:
    path = SEED_DIR / name
    if not path.exists():
        raise SystemExit(f"缺种子文件：{path}")
    out = []
    with path.open(encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            missing = [c for c in cols if c not in r]
            if missing:
                raise SystemExit(f"{name} 第 {i} 行缺列：{', '.join(missing)}")
            out.append(tuple((r[c].strip() or None) for c in cols))
    return out


def load(cfg: Config) -> int:
    with onto_conn(cfg) as conn:
        # 先按反序删除已不在 CSV 里的行，外键才不会挡路
        loaded: list[tuple[str, str, list[tuple]]] = []
        for fname, table, pk, cols in SPECS:
            loaded.append((table, pk, _read(fname, cols)))

        for (table, pk, rows), (_, _, _, cols) in zip(reversed(loaded),
                                                      reversed(SPECS), strict=True):
            keys = [r[cols.index(pk)] for r in rows]
            conn.execute(
                f"DELETE FROM diabetes.{table} WHERE {pk} <> ALL(%s)", (keys or [""],)
            )

        for (table, pk, rows), (fname, _, _, cols) in zip(loaded, SPECS, strict=True):
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != pk)
            stmt = (
                f"INSERT INTO diabetes.{table} ({', '.join(cols)}) "
                f"VALUES ({', '.join(['%s'] * len(cols))}) "
                f"ON CONFLICT ({pk}) DO UPDATE SET {updates}"
            )
            with conn.cursor() as cur:
                cur.executemany(stmt, rows)
            print(f"  ✓ {fname:<30} → diabetes.{table:<22} {len(rows):>3} 行")
        conn.commit()

        print()
        scen = conn.fetchall(
            "SELECT demo_scenario, count(*) n FROM diabetes.sim_patient "
            "GROUP BY 1 ORDER BY 1"
        )
        print(f"✓ {sum(s['n'] for s in scen)} 例演示患者，覆盖 {len(scen)} 个场景：")
        print("   ", "  ".join(f"{s['demo_scenario']}×{s['n']}" for s in scen))
    return 0
