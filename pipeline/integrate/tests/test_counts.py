"""Regression gate: merged line counts for universe/test-small."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MERGED = REPO / "universe/test-small/4-merged"


def test_test_small_merged_line_counts():
    nodes = MERGED / "nodes.jsonl"
    edges = MERGED / "edges.jsonl"
    assert nodes.is_file()
    assert edges.is_file()
    node_count = sum(1 for line in nodes.open("rb") if line.strip())
    edge_count = sum(1 for line in edges.open("rb") if line.strip())
    assert node_count == 105
    assert edge_count == 38
