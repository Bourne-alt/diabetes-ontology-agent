"""Insert only the requested synthetic P0002, refusing to overwrite existing data.

Usage: PYTHONPATH=src python scripts/seed_patient_p0002.py [--apply]
This core-only fixture avoids relaxing the sim_patient P9xxxx constraint.
A full `dmo project run` rebuild clears it; rerun this script and patient sync then.
"""

import argparse
import json
from pathlib import Path

from psycopg import sql

from dmo.config import load
from dmo.db.engine import onto_conn

FIXTURE = Path(__file__).resolve().parents[1] / "demo/patient-p0002.json"
TABLES = {
    "core_patient": "patientid",
    "core_encounter": "encounter_id",
    "core_lab_result": "lab_result_id",
    "core_observation": "observation_id",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    batches = json.loads(FIXTURE.read_text())["tables"]
    if set(batches) != set(TABLES):
        raise ValueError("Unexpected fixture tables")
    for table, rows in batches.items():
        for row in rows:
            if (row["patientid"] != "P0002" or row["fact_origin"] != "demo-cohort"
                    or row["source_table"] != "fixture:demo/patient-p0002.json"):
                raise ValueError("Fixture must contain only synthetic P0002 records")
    counts = {table: len(rows) for table, rows in batches.items()}
    if args.apply:
        with onto_conn(load()) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(9200002)")
            for table in (*TABLES, "core_diagnosis", "core_medication_use", "stg_patient_basic"):
                found = conn.fetchone(sql.SQL(
                    "SELECT patientid FROM diabetes.{} WHERE patientid = %s LIMIT 1"
                ).format(sql.Identifier(table)), ("P0002",))
                if found:
                    raise ValueError(f"P0002 already exists in {table}; refusing to overwrite")
            for table, rows in batches.items():
                for row in rows:
                    conn.execute(sql.SQL("INSERT INTO diabetes.{} ({}) VALUES ({})").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(map(sql.Identifier, row)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in row),
                    ), tuple(row.values()))
            conn.commit()
    print(json.dumps({"applied": args.apply, "patientid": "P0002", "rows": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
