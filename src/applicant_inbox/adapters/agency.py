"""Employment-agency portal: one JSON document with nested applicant objects."""

from __future__ import annotations

import json
from datetime import datetime

from ..models import Application, ParseResult
from ..normalize import to_utc_iso


def parse(path: str) -> ParseResult:
    result = ParseResult()
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    for index, item in enumerate(document.get("applications", []), start=1):
        try:
            applicant = item.get("applicant", {})
            contact = applicant.get("contact", {})
            created = to_utc_iso(datetime.fromisoformat(item["created"].replace("Z", "+00:00")))
            name = "%s %s" % (applicant.get("given", ""), applicant.get("surname", ""))
            result.applications.append(Application.build(
                "agency", item["ref"], created, name, contact.get("email_address", ""),
                contact.get("mobile", ""), item.get("remark", "")))
        except (ValueError, KeyError, AttributeError) as exc:
            result.errors.append("application #%d: %s" % (index, exc))
    return result
