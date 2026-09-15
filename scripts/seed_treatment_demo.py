"""Seed the owned P91001–P91008 synthetic assessment scenarios."""
import argparse
import json
from datetime import date

from dmo.assessment.demo import catalog, seed
from dmo.config import load

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-date", type=date.fromisoformat)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    print(json.dumps(catalog() if args.list else seed(load(), args.reference_date), ensure_ascii=False, indent=2))
