"""Duplicate detection: which applications came from the same person?

Two applications are linked when they share a normalised e-mail address **or** phone number **and**
their names do not contradict each other. Links are joined transitively (union-find), so a person who
applied through three channels ends up as one candidate.

The name check is what keeps shared contacts from merging strangers: a family phone, a team mailbox
or an agency's `bewerbung@` address appears on applications of *different* people.
Because links are transitive, a nameless message (a chat with only a phone number) can bridge two people
who share that number - such groups are kept but flagged `needs_review`.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from .models import Application, Candidate
from .normalize import name_key, name_tokens, names_compatible


class _UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[max(root_a, root_b)] = min(root_a, root_b)


def _best_name(apps: Sequence[Application]) -> str:
    """Prefer the most complete name; among equals the 'First Last' spelling over 'Last, First'."""
    names = [a.name for a in apps if a.name]
    if not names:
        return ""
    return max(names, key=lambda n: (len(name_tokens(n)), "," not in n, len(n)))


def _all_compatible(apps: Sequence[Application]) -> bool:
    named = [a.name for a in apps if a.name]
    return all(names_compatible(x, y) for i, x in enumerate(named) for y in named[i + 1:])


def cluster(applications: Sequence[Application]) -> List[Candidate]:
    apps = list(applications)
    groups = _UnionFind(len(apps))
    buckets: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for index, app in enumerate(apps):
        if app.email:
            buckets[("email", app.email)].append(index)
        if app.phone:
            buckets[("phone", app.phone)].append(index)
    for members in buckets.values():
        for position, i in enumerate(members):
            for j in members[position + 1:]:
                if names_compatible(apps[i].name, apps[j].name):
                    groups.union(i, j)

    clusters: Dict[int, List[Application]] = defaultdict(list)
    for index, app in enumerate(apps):
        clusters[groups.find(index)].append(app)

    candidates = []
    for members in clusters.values():
        members.sort(key=lambda a: (a.received_at, a.key))
        earliest = members[0]
        candidate_id = "C" + hashlib.sha1(earliest.key.encode("utf-8")).hexdigest()[:8]
        timestamps = [a.received_at for a in members if a.received_at]
        candidates.append(Candidate(
            candidate_id=candidate_id,
            name=_best_name(members),
            emails=sorted({a.email for a in members if a.email}),
            phones=sorted({a.phone for a in members if a.phone}),
            sources=sorted({a.source for a in members}),
            first_seen=min(timestamps) if timestamps else "",
            last_seen=max(timestamps) if timestamps else "",
            application_keys=[a.key for a in members],
            latest_message=members[-1].message,
            needs_review=not _all_compatible(members),
        ))
    candidates.sort(key=lambda c: (c.first_seen, c.candidate_id))
    return candidates


def possible_duplicates(candidates: Sequence[Candidate]) -> List[List[Candidate]]:
    """Candidates with the same full name but no shared contact. They are NOT merged automatically -
    a name alone is not an identity - but a recruiter should look at them."""
    by_name: Dict[str, List[Candidate]] = defaultdict(list)
    for candidate in candidates:
        key = name_key(candidate.name)
        if len(key.split()) >= 2:
            by_name[key].append(candidate)
    return [group for group in by_name.values() if len(group) > 1]
