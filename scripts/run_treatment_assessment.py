"""Create JSON/Markdown artifacts from an explicit standardized patient snapshot."""

import argparse
import json
from pathlib import Path

from dmo.assessment.contracts import TreatmentAssessmentRequest
from dmo.assessment.service import assess
from dmo.assessment.storage import archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--composer", choices=["template", "auto", "llm"])
    parser.add_argument("--out", type=Path, default=Path("outputs/treatment-assessments"))
    args = parser.parse_args()
    data = json.loads(args.request.read_text())
    if args.composer:
        data["composer"] = args.composer
    report = assess(args.patient, TreatmentAssessmentRequest.model_validate(data))
    archive(report, args.out)
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "status": report["status"],
                "composer": report["generation_metadata"]["composer"],
                "fallback_reason": report["generation_metadata"].get("fallback_reason"),
                "markdown": str((args.out / (report["report_id"] + ".md")).resolve()),
                "claim_count": len(report["claims"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
