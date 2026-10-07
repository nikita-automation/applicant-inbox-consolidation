"""SQLite storage. Ingest is idempotent: (source, source_id) is unique, so re-importing an export
never creates duplicates. Candidates are derived data and are rebuilt from scratch on every merge."""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable, List, Tuple

from .models import Application, Candidate

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    received_at TEXT NOT NULL,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT NOT NULL,
    raw_email   TEXT NOT NULL,
    raw_phone   TEXT NOT NULL,
    message     TEXT NOT NULL,
    UNIQUE (source, source_id)
);
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    emails       TEXT NOT NULL,
    phones       TEXT NOT NULL,
    sources      TEXT NOT NULL,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    applications TEXT NOT NULL,
    latest_message TEXT NOT NULL,
    needs_review INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def add_applications(self, applications: Iterable[Application]) -> Tuple[int, int]:
        """Insert applications; returns (new, already_known)."""
        new = known = 0
        with self.connection:
            for app in applications:
                cursor = self.connection.execute(
                    "INSERT OR IGNORE INTO applications (source, source_id, received_at, name, email, phone,"
                    " raw_email, raw_phone, message) VALUES (?,?,?,?,?,?,?,?,?)",
                    (app.source, app.source_id, app.received_at, app.name, app.email, app.phone,
                     app.raw_email, app.raw_phone, app.message))
                if cursor.rowcount:
                    new += 1
                else:
                    known += 1
        return new, known

    def applications(self) -> List[Application]:
        rows = self.connection.execute(
            "SELECT * FROM applications ORDER BY received_at, source, source_id").fetchall()
        return [Application(source=r["source"], source_id=r["source_id"], received_at=r["received_at"],
                            name=r["name"], email=r["email"], phone=r["phone"], message=r["message"],
                            raw_email=r["raw_email"], raw_phone=r["raw_phone"], id=r["id"]) for r in rows]

    def replace_candidates(self, candidates: Iterable[Candidate]) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM candidates")
            for c in candidates:
                self.connection.execute(
                    "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (c.candidate_id, c.name, json.dumps(c.emails), json.dumps(c.phones),
                     json.dumps(c.sources), c.first_seen, c.last_seen, json.dumps(c.application_keys),
                     c.latest_message, int(c.needs_review)))

    def candidates(self) -> List[Candidate]:
        rows = self.connection.execute(
            "SELECT * FROM candidates ORDER BY first_seen, candidate_id").fetchall()
        return [Candidate(candidate_id=r["candidate_id"], name=r["name"], emails=json.loads(r["emails"]),
                          phones=json.loads(r["phones"]), sources=json.loads(r["sources"]),
                          first_seen=r["first_seen"], last_seen=r["last_seen"],
                          application_keys=json.loads(r["applications"]),
                          latest_message=r["latest_message"], needs_review=bool(r["needs_review"]))
                for r in rows]

    def counts_by_source(self) -> List[Tuple[str, int]]:
        rows = self.connection.execute(
            "SELECT source, COUNT(*) AS n FROM applications GROUP BY source ORDER BY source").fetchall()
        return [(r["source"], r["n"]) for r in rows]
