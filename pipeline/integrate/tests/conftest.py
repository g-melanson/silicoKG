from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.integrate.engine import integrate_silver_paths
from pipeline.integrate.priorities import IntegratePriorities, load_priorities

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def priorities() -> IntegratePriorities:
    return load_priorities(REPO / "schemas" / "integrate-priorities.yaml")


def run_integrate(path: Path, priorities: IntegratePriorities):
    nodes, edges, quarantine, summary = integrate_silver_paths([path], priorities)
    return list(nodes), list(edges), quarantine, summary
