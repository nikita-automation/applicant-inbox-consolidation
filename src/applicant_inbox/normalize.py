"""Normalisation of the three things we match on: phone numbers, e-mail addresses and names.

Matching on raw strings fails constantly ("030 23125 001" vs "+49 (0) 30 23125001"), so every
contact value is reduced to one canonical form first. The raw value is kept next to it for audit.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import List, Optional

try:  # zoneinfo is in the standard library from Python 3.9
    from zoneinfo import ZoneInfo
    _LOCAL = ZoneInfo("Europe/Berlin")
except Exception:  # pragma: no cover - tz database missing
    _LOCAL = None

DEFAULT_COUNTRY_CODE = "49"

# --- phone ------------------------------------------------------------------------------

_PHONE_WITH_LABEL = re.compile(
    r"(?:tel(?:efon)?|mobil(?:e)?|handy|phone|fon|mob)\.?\s*[:\-]?\s*"
    r"(\+?[\d(][\d\s()./-]{6,}\d)", re.IGNORECASE)
_PHONE_WITH_PLUS = re.compile(r"(\+\d[\d\s()./-]{7,}\d)")


def normalize_phone(raw: Optional[str], country_code: str = DEFAULT_COUNTRY_CODE) -> str:
    """Return the number as '+<country><digits>' or '' if it cannot be interpreted.

    Handles national format (0151...), '00' international prefix, '+49 (0) 151...' and the
    common typo '+49 0151...'. Numbers without any prefix and without a leading zero (e.g. '123')
    are rejected rather than guessed.
    """
    if not raw:
        return ""
    text = re.sub(r"\(0\)", "", raw.strip())
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if text.lstrip().startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = country_code + digits[1:]
    elif digits.startswith(country_code) and len(digits) >= 11:
        pass  # exported without the '+'
    else:
        return ""
    if digits.startswith(country_code + "0"):
        digits = country_code + digits[len(country_code) + 1:]   # '+49 0151' -> '+49 151'
    if not 8 <= len(digits) <= 15:
        return ""
    return "+" + digits


def find_phone_in_text(text: str) -> str:
    """Pick a phone number out of free text (an e-mail signature, a chat message).

    Only numbers with a label ('Tel.', 'Mobil') or a leading '+' are considered - a bare run of
    digits would turn dates like 05.10.2026 into phone numbers.
    """
    for pattern in (_PHONE_WITH_LABEL, _PHONE_WITH_PLUS):
        for match in pattern.finditer(text or ""):
            number = normalize_phone(match.group(1))
            if number:
                return number
    return ""


# --- e-mail -----------------------------------------------------------------------------

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(raw: Optional[str]) -> str:
    """Lower-case and trim. Dots and '+tags' are left alone: stripping them is only valid for some
    providers and would merge strangers."""
    if not raw:
        return ""
    text = raw.strip()
    if text.lower().startswith("mailto:"):
        text = text[7:]
    text = text.strip().strip("<>").lower()
    return text if _EMAIL.match(text) else ""


# --- names ------------------------------------------------------------------------------

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                          "Ä": "ae", "Ö": "oe", "Ü": "ue"})
_TITLES = {"dr", "prof", "herr", "frau", "mr", "mrs", "ms", "mag", "dipl", "ing"}


def name_tokens(name: Optional[str]) -> List[str]:
    """'Müller, Dr. Clara' -> ['clara', 'mueller']: umlauts spelled out, accents dropped, titles removed,
    'Last, First' reordered."""
    if not name:
        return []
    text = name.strip()
    if "," in text:
        last, _, first = text.partition(",")
        text = first + " " + last
    text = text.translate(_UMLAUTS).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return [t for t in re.findall(r"[a-z0-9]+", text) if t not in _TITLES]


def name_key(name: Optional[str]) -> str:
    return " ".join(sorted(name_tokens(name)))


def _covers(small: List[str], big: List[str]) -> bool:
    """Every token of `small` appears in `big` (a single letter counts as an initial)."""
    for token in small:
        if token in big:
            continue
        if len(token) == 1 and any(other.startswith(token) for other in big):
            continue
        return False
    return True


def names_compatible(a: Optional[str], b: Optional[str]) -> bool:
    """Could these two names belong to the same person?

    A missing name never contradicts anything (a chat message often has only a phone number).
    Otherwise one name must be contained in the other: 'Anna Beispiel' ~ 'A. Beispiel' ~
    'Beispiel, Anna-Lena', but 'Ida Muster' !~ 'Jan Muster'.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return True
    return _covers(ta, tb) or _covers(tb, ta)


# --- time -------------------------------------------------------------------------------

def to_utc_iso(value: datetime) -> str:
    """ISO 8601 in UTC. Naive timestamps are read as Europe/Berlin local time."""
    if value.tzinfo is None:
        if _LOCAL is not None:
            value = value.replace(tzinfo=_LOCAL)
        else:  # pragma: no cover
            value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
