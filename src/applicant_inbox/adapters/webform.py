"""Website form submissions: one JSON object per line (webhook log)."""

from __future__ import annotations

import json
from datetime import datetime

from ..models import Application, ParseResult
from ..normalize import to_utc_iso


def parse(path: str) -> ParseResult:
    result = ParseResult()
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                submitted = to_utc_iso(datetime.fromisoformat(row["submitted"]))
                result.applications.append(Application.build(
                    "webform", row["id"], submitted, row.get("fullName", ""),
                    row.get("mail", ""), row.get("tel", ""), row.get("message", "")))
            except (ValueError, KeyError, TypeError) as exc:
                result.errors.append("line %d: %s" % (number, exc))
    return result
