from __future__ import annotations

import json

from pipeline.integrate.tests.conftest import run_integrate
from pipeline.integrate.tests.silver_fixtures import (
    gene_fragment,
    maps_gene_fragment,
    write_silver,
)


def test_integrate_single_gene_fragment(tmp_path, priorities):
    silver = write_silver(tmp_path, [gene_fragment(symbol="A1BG")])
    nodes, edges, quarantine, summary = run_integrate(silver, priorities)

    assert quarantine == []
    assert summary.fragment_count == 1
    assert summary.node_count == 1
    assert summary.edge_count == 0
    assert len(nodes) == summary.node_count
    assert edges == []


def test_integrate_node_and_edge(tmp_path, priorities):
    silver = write_silver(
        tmp_path,
        [
            gene_fragment(symbol="A1BG"),
            maps_gene_fragment(bronze_line=1),
        ],
    )
    nodes, edges, quarantine, summary = run_integrate(silver, priorities)

    assert quarantine == []
    assert summary.fragment_count == 2
    assert summary.node_count == 1
    assert summary.edge_count == 1
    assert len(nodes) == 1
    assert len(edges) == 1


def test_integrate_silver_paths_generates_summary(tmp_path, priorities):
    silver = write_silver(tmp_path, [gene_fragment(symbol="A1BG")])
    _, _, _, summary = run_integrate(silver, priorities)

    assert summary.sources == [str(silver)]
    assert summary.edge_payload_conflict_samples == []


def test_integrate_silver_paths_populates_summary(tmp_path, priorities):
    silver = write_silver(
        tmp_path,
        [
            gene_fragment(symbol="A1BG"),
            maps_gene_fragment(bronze_line=1),
        ],
    )
    _, _, _, summary = run_integrate(silver, priorities)

    assert summary.fragment_count == 2
    assert summary.node_count == 1
    assert summary.edge_count == 1
    assert summary.quarantine_count == 0
    assert summary.edge_payload_conflicts == 0


def test_integrate_three_sources_merge_one_node(tmp_path, priorities):
    silver = write_silver(
        tmp_path,
        [
            gene_fragment(
                symbol="A1BG",
                name="alpha-1-B glycoprotein",
                description="from gene-info",
                synonyms=["A1BG", "A1B"],
            ),
            gene_fragment(
                source_name="ncbi-gene-summary",
                bronze_line=1,
                description="from gene-summary",
                synonyms=["A1B", "GAB"],
            ),
            gene_fragment(
                source_name="uniprot-gaf",
                bronze_line=2,
                symbol="A1BG_HUMAN",
                description="from uniprot",
                synonyms=["HEL-S-163pA"],
            ),
        ],
    )
    nodes, edges, quarantine, summary = run_integrate(silver, priorities)

    assert quarantine == []
    assert summary.fragment_count == 3
    assert summary.node_count == 1
    assert edges == []
    node = nodes[0]
    assert len(node["sources"]) == 3
    assert "alternates" in node


def test_integrate_three_sources_merge_one_edge(tmp_path, priorities):
    silver = write_silver(
        tmp_path,
        [
            maps_gene_fragment(bronze_line=1),
            maps_gene_fragment(
                source_name="ncbi-gene-info",
                bronze_line=2,
            ),
            maps_gene_fragment(
                source_name="uniprot-gaf",
                bronze_line=3,
                start="999",
                end="888",
                status="MODEL",
            ),
        ],
    )
    nodes, edges, quarantine, summary = run_integrate(silver, priorities)

    assert nodes == []
    assert quarantine == []
    assert summary.fragment_count == 3
    assert summary.edge_count == 1
    assert summary.edge_payload_conflicts == 3
    edge = edges[0]
    assert len(edge["sources"]) == 3
    assert len(summary.edge_payload_conflict_samples) == 3


def test_integrate_silver_paths_writes_quarantine(tmp_path, priorities):
    bad = {
        "class": "Gene",
        "object": {"@type": "Gene"},  # missing id
        "source": {
            "source_name": "ncbi-gene-info",
            "silver_run_id": "test-run",
            "bronze_line": 0,
        },
    }
    silver = write_silver(tmp_path, [bad])
    nodes, edges, quarantine, summary = run_integrate(silver, priorities)

    assert nodes == []
    assert edges == []
    assert summary.quarantine_count == 1
    assert summary.fragment_count == 1
    assert quarantine[0]["errors"]


def test_integrate_silver_paths_lines_are_counted(tmp_path, priorities):
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(
        "\n".join(
            [
                "",  # blank line — not counted
                json.dumps(gene_fragment(symbol="A1BG")),
                json.dumps(maps_gene_fragment(bronze_line=1)),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _, _, _, summary = run_integrate(silver, priorities)

    assert summary.fragment_count == 2
    assert summary.node_count == 1
    assert summary.edge_count == 1
