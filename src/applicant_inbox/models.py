"""Data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .normalize import normalize_email, normalize_phone


@dataclass
class Application:
    """One incoming application, as received through one channel."""

    source: str                 # adapter name, e.g. 'webform'
    source_id: str              # id of the application inside that channel (stable across re-imports)
    received_at: str            # ISO 8601 UTC, '' if the channel gave no timestamp
    name: str = ""
    email: str = ""             # normalised
    phone: str = ""             # normalised E.164-style
    message: str = ""
    raw_email: str = ""
    raw_phone: str = ""
    id: Optional[int] = None    # database row id once stored

    @classmethod
    def build(cls, source: str, source_id: str, received_at: str, name: str = "",
              email: str = "", phone: str = "", message: str = "") -> "Application":
        """Create an application and normalise its contact values."""
        return cls(source=source, source_id=str(source_id), received_at=received_at or "",
                   name=" ".join((name or "").split()), email=normalize_email(email),
                   phone=normalize_phone(phone), message=(message or "").strip(),
                   raw_email=(email or "").strip(), raw_phone=(phone or "").strip())

    @property
    def key(self) -> str:
        return "%s:%s" % (self.source, self.source_id)

    @property
    def has_contact(self) -> bool:
        return bool(self.email or self.phone)


@dataclass
class ParseResult:
    applications: List[Application] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class Candidate:
    """One person - the merge of every application we think came from them."""

    candidate_id: str
    name: str
    emails: List[str]
    phones: List[str]
    sources: List[str]
    first_seen: str
    last_seen: str
    application_keys: List[str]
    latest_message: str = ""
    needs_review: bool = False   # members include names that contradict each other

    @property
    def applications(self) -> int:
        return len(self.application_keys)
