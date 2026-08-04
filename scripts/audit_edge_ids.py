"""Audit edge id uniqueness in a JSONL edges file.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/audit_edge_ids.py universe/<run>/5-gold/edges.jsonl

Exits non-zero if any edge id occurs more than once.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from pipeline.io.jsonl import loads_line


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: audit_edge_ids.py <edges.jsonl>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    counts: Counter[str] = Counter()
    for line in path.open("rb"):
        if not line.strip():
            continue
        edge = loads_line(line)
        counts[edge["id"]] += 1
    dups = {edge_id: n for edge_id, n in counts.items() if n > 1}
    print(
        f"edges={sum(counts.values())} unique_ids={len(counts)} "
        f"duplicate_ids={len(dups)}"
    )
    if dups:
        for edge_id, n in list(dups.items())[:10]:
            print(f"  {edge_id} x{n}")
    return 1 if dups else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
