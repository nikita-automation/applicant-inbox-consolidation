"""Mailbox export: a directory of .eml files. The phone number is taken from the signature if present."""

from __future__ import annotations

import hashlib
import os
from email import policy
from email.parser import BytesParser

from ..models import Application, ParseResult
from ..normalize import find_phone_in_text, to_utc_iso


def _parse_file(path: str) -> Application:
    with open(path, "rb") as handle:
        message = BytesParser(policy=policy.default).parse(handle)
    sender = message["From"].addresses[0] if message["From"] and message["From"].addresses else None
    if sender is None:
        raise ValueError("no usable From header")
    body_part = message.get_body(preferencelist=("plain",))
    body = body_part.get_content() if body_part is not None else ""
    date = message["Date"].datetime if message["Date"] else None
    message_id = (message["Message-ID"] or "").strip()
    if message_id:
        source_id = message_id
    else:
        with open(path, "rb") as handle:
            source_id = hashlib.sha1(handle.read()).hexdigest()[:12]
    subject = (message["Subject"] or "").strip()
    return Application.build(
        "mail", source_id, to_utc_iso(date) if date else "", sender.display_name,
        sender.addr_spec, find_phone_in_text(body), (subject + "\n" + body).strip()[:500])


def parse(path: str) -> ParseResult:
    result = ParseResult()
    names = sorted(os.listdir(path)) if os.path.isdir(path) else [None]
    for name in names:
        file_path = os.path.join(path, name) if name else path
        if name and not name.lower().endswith(".eml"):
            continue
        try:
            result.applications.append(_parse_file(file_path))
        except (ValueError, KeyError, AttributeError, OSError) as exc:
            result.errors.append("%s: %s" % (name or os.path.basename(file_path), exc))
    return result
