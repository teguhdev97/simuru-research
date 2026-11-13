from __future__ import annotations

import csv
from io import StringIO
from typing import Iterable


def results_to_csv(rows: Iterable[dict[str, object]]) -> str:
    output = StringIO()
    fieldnames = [
        "job_index",
        "username",
        "email",
        "phone",
        "status",
        "duration_ms",
        "error",
        "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
