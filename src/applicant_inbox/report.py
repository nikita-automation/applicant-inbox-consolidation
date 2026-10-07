"""Text report and CSV export."""

from __future__ import annotations

import csv
import io
from typing import List, Sequence

from .dedupe import possible_duplicates
from .models import Application, Candidate


def summary_lines(applications: Sequence[Application], candidates: Sequence[Candidate],
                  per_source: Sequence[tuple]) -> List[str]:
    merged_away = len(applications) - len(candidates)
    review = [c for c in candidates if c.needs_review]
    no_contact = [a for a in applications if not a.has_contact]
    lines = ["%d applications from %d sources -> %d candidates (%d duplicates merged, %d group(s) need review)"
             % (len(applications), len(per_source), len(candidates), merged_away, len(review)), ""]
    lines.append("Per source: " + ", ".join("%s %d" % (name, count) for name, count in per_source))
    lines.append("")

    merged = [c for c in candidates if c.applications > 1]
    lines.append("Merged candidates (%d):" % len(merged))
    for c in merged:
        flag = "  [REVIEW]" if c.needs_review else ""
        lines.append("  %s  %-22s %d applications via %s%s"
                     % (c.candidate_id, c.name or "(no name)", c.applications, "+".join(c.sources), flag))
    if review:
        lines += ["", "Needs review - names in this group contradict each other:"]
        for c in review:
            lines.append("  %s  %s" % (c.candidate_id, ", ".join(c.application_keys)))

    duplicates = possible_duplicates(candidates)
    if duplicates:
        lines += ["", "Possible duplicates - same name, no shared contact (not merged):"]
        for group in duplicates:
            lines.append("  %s  -> %s" % (group[0].name, ", ".join(c.candidate_id for c in group)))

    if no_contact:
        lines += ["", "Applications without any usable e-mail or phone (%d): %s"
                  % (len(no_contact), ", ".join(a.key for a in no_contact))]
    return lines


def candidates_csv(candidates: Sequence[Candidate]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["candidate_id", "name", "emails", "phones", "sources", "applications",
                     "first_seen", "last_seen", "needs_review"])
    for c in candidates:
        writer.writerow([c.candidate_id, c.name, " | ".join(c.emails), " | ".join(c.phones),
                         " | ".join(c.sources), c.applications, c.first_seen, c.last_seen,
                         "yes" if c.needs_review else ""])
    return buffer.getvalue()
