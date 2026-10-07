"""Job board B: CSV export, German headers, semicolon separated, first and last name in separate columns."""

from __future__ import annotations

import csv
from datetime import datetime

from ..models import Application, ParseResult
from ..normalize import to_utc_iso


def parse(path: str) -> ParseResult:
    result = ParseResult()
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle, delimiter=";"), start=2):
            try:
                received = to_utc_iso(datetime.strptime(row["Eingang"].strip(), "%d.%m.%Y %H:%M"))
                name = "%s %s" % (row.get("Vorname", ""), row.get("Nachname", ""))
                result.applications.append(Application.build(
                    "board_b", row["Bewerbungsnr"].strip(), received, name,
                    row.get("E-Mail", ""), row.get("Telefon", ""), row.get("Anschreiben", "")))
            except (ValueError, KeyError, AttributeError) as exc:
                result.errors.append("row %d: %s" % (number, exc))
    return result
