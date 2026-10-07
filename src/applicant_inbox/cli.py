"""Command line interface: `python -m applicant_inbox ...`"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .adapters import ADAPTERS, DEFAULT_PATHS
from .dedupe import cluster
from .report import candidates_csv, summary_lines
from .store import Store


def _ingest(store: Store, adapter: str, path: str) -> None:
    result = ADAPTERS[adapter](path)
    new, known = store.add_applications(result.applications)
    print("%-8s %s: %d read, %d new, %d already known, %d unreadable"
          % (adapter, path, len(result.applications), new, known, len(result.errors)))
    for error in result.errors:
        print("         ! " + error)


def _merge(store: Store) -> None:
    candidates = cluster(store.applications())
    store.replace_candidates(candidates)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="applicant_inbox", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--db", default="inbox.db", help="SQLite file (default: inbox.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("ingest", help="import one export")
    one.add_argument("adapter", choices=sorted(ADAPTERS))
    one.add_argument("path")

    every = sub.add_parser("ingest-dir", help="import all sample-style exports from a directory")
    every.add_argument("directory")

    sub.add_parser("merge", help="(re)build the deduplicated candidate list")
    sub.add_parser("report", help="print the summary")
    exp = sub.add_parser("export", help="write the candidates as CSV")
    exp.add_argument("--out", default="-", help="file path, or - for stdout")
    demo = sub.add_parser("demo", help="ingest + merge + report in one go")
    demo.add_argument("directory", nargs="?", default=os.path.join("data", "sample"))

    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
        if args.command == "ingest":
            _ingest(store, args.adapter, args.path)
        elif args.command in ("ingest-dir", "demo"):
            for adapter, relative in DEFAULT_PATHS.items():
                _ingest(store, adapter, os.path.join(args.directory, relative))
            _merge(store)
            if args.command == "demo":
                print()
                print("\n".join(summary_lines(store.applications(), store.candidates(), store.counts_by_source())))
        elif args.command == "merge":
            _merge(store)
            print("%d candidates" % len(store.candidates()))
        elif args.command == "report":
            print("\n".join(summary_lines(store.applications(), store.candidates(), store.counts_by_source())))
        elif args.command == "export":
            text = candidates_csv(store.candidates())
            if args.out == "-":
                sys.stdout.write(text)
            else:
                with open(args.out, "w", encoding="utf-8", newline="") as handle:
                    handle.write(text)
                print("wrote %s" % args.out)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
