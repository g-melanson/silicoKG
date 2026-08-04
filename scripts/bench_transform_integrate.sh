#!/usr/bin/env bash
# Print transform/integrate timings from universe manifests.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_ID="${1:-test-small}"
UNIVERSE="${UNIVERSE:-universe}"

RUN_ID="$RUN_ID" UNIVERSE="$UNIVERSE" python3 - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path

run_id = os.environ["RUN_ID"]
root = Path(os.environ["UNIVERSE"]) / run_id
print(f"run_id={run_id}")
print(f"{'stage':12} {'source':22} {'duration_s':>10} {'fragments':>12}")
print("-" * 60)


def duration(data, end_key="ended_at"):
    if data.get("duration_seconds") is not None:
        return data["duration_seconds"]
    start = data.get("started_at")
    end = data.get(end_key)
    if start and end:
        return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    return None


for manifest in sorted(root.glob("3-silver/*/manifest.json")):
    data = json.loads(manifest.read_text())
    dur = duration(data, "ended_at")
    frags = data.get("drift", {}).get("accepted_count", "")
    print(
        f"{'transform':12} {data.get('source_name', ''):22} "
        f"{dur if dur is not None else '-':>10} {frags:>12}"
    )

merged = root / "4-merged" / "manifest.json"
if merged.is_file():
    data = json.loads(merged.read_text())
    dur = duration(data, "finished_at")
    frags = data.get("drift", {}).get("fragment_count", "")
    print(
        f"{'integrate':12} {'(merged)':22} "
        f"{dur if dur is not None else '-':>10} {frags:>12}"
    )
PY
