"""Chat export: a text file with one message per line, 'DD.MM.YY, HH:MM - sender: text'.

The sender is either a phone number or a saved contact name. Lines without a timestamp continue the
previous message; timestamped lines without a sender are system notices and are skipped.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import List, Optional

from ..models import Application, ParseResult
from ..normalize import normalize_phone, to_utc_iso

_MESSAGE = re.compile(r"^(\d{2}\.\d{2}\.\d{2,4}), (\d{1,2}:\d{2}) - ([^:]+): (.*)$")
_TIMESTAMP = re.compile(r"^\d{2}\.\d{2}\.\d{2,4}, \d{1,2}:\d{2} - ")


def _timestamp(day: str, clock: str) -> datetime:
    fmt = "%d.%m.%Y %H:%M" if len(day.split(".")[-1]) == 4 else "%d.%m.%y %H:%M"
    return datetime.strptime("%s %s" % (day, clock), fmt)


def parse(path: str) -> ParseResult:
    result = ParseResult()
    current: Optional[dict] = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        raw = current
        current = None
        text = "\n".join(raw["lines"]).strip()
        sender = raw["sender"].strip().lstrip("~").strip()
        phone = normalize_phone(sender)
        name = "" if phone else sender
        digest = hashlib.sha1(("%s|%s|%s" % (raw["stamp"], sender, text)).encode("utf-8")).hexdigest()[:12]
        result.applications.append(Application.build(
            "chat", digest, to_utc_iso(_timestamp(*raw["stamp"].split("|"))), name, "",
            sender if phone else "", text))

    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            match = _MESSAGE.match(line)
            if match:
                flush()
                try:
                    _timestamp(match.group(1), match.group(2))
                except ValueError as exc:
                    result.errors.append("line %d: %s" % (number, exc))
                    continue
                current = {"stamp": "%s|%s" % (match.group(1), match.group(2)),
                           "sender": match.group(3), "lines": [match.group(4)]}
            elif _TIMESTAMP.match(line):
                flush()                      # system notice
            elif current is not None and line.strip():
                current["lines"].append(line)
        flush()
    return result
