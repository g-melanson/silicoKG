"""Regression gate: merged line counts for the NCBI small fixture set.

Counts the checked-in snapshots under fixtures/test-small-merged/ rather than
gitignored universe/test-small/4-merged/. Snapshots come from ingest → transform
→ integrate of fixtures/ncbi/{Homo_sapiens.gene_info,gene_summary,gene2refseq}.small.tsv.
"""

from __future__ import annotations

from pathlib import Path

MERGED = Path(__file__).resolve().parent / "fixtures" / "test-small-merged"


def test_test_small_merged_line_counts():
    nodes = MERGED / "nodes.jsonl"
    edges = MERGED / "edges.jsonl"
    assert nodes.is_file()
    assert edges.is_file()
    node_count = sum(1 for line in nodes.open("rb") if line.strip())
    edge_count = sum(1 for line in edges.open("rb") if line.strip())
    assert node_count == 71
    assert edge_count == 90
