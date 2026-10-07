"""Job board A: CSV export, English headers, comma separated, date only."""

from __future__ import annotations

import csv
from datetime import datetime

from ..models import Application, ParseResult
from ..normalize import to_utc_iso


def parse(path: str) -> ParseResult:
    result = ParseResult()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):   # row 1 = header
            try:
                received = to_utc_iso(datetime.strptime(row["Date"].strip(), "%Y-%m-%d"))
                result.applications.append(Application.build(
                    "board_a", row["Application ID"].strip(), received, row.get("Candidate", ""),
                    row.get("Email", ""), row.get("Phone", ""), row.get("Cover note", "")))
            except (ValueError, KeyError, AttributeError) as exc:
                result.errors.append("row %d: %s" % (number, exc))
    return result
