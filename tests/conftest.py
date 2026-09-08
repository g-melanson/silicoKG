from __future__ import annotations

from pathlib import Path

import json
import pytest

from pipeline.integrate.priorities import IntegratePriorities, load_priorities
from pipeline.paths import REPO_ROOT


@pytest.fixture(scope="module")
def priorities() -> IntegratePriorities:
    return load_priorities(REPO_ROOT / "schemas" / "integrate-priorities.yaml")

def _write_jsonl(
    tmp_path: Path,
    records: list[dict],
    name: str = "records",
) -> Path:
    path = tmp_path / f"{name}.jsonl"
    path.write_text(
        "".join(json.dumps(f) + "\n" for f in records), 
        encoding="utf-8"
    )
    return path

def _read_jsonl(
    path: Path,
) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
