"""Optional private artifact archive; never writes to clinical databases."""

import json
import os
import tempfile
from pathlib import Path


def archive(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for suffix, text in (
        ("json", json.dumps(report, ensure_ascii=False, indent=2)),
        ("md", report["rendered_markdown"]),
    ):
        fd, temp = tempfile.mkstemp(prefix=".assessment-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
            os.replace(temp, directory / f"{report['report_id']}.{suffix}")
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
