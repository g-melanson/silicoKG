from __future__ import annotations

import json
from pathlib import Path

from pipeline.publish.engine import PublishSummary, publish_merged_paths

REPO = Path(__file__).resolve().parents[3]
SCHEMA = REPO / "schemas" / "domain" / "gene-or-gene-product.yaml"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _collect(nodes_path: Path, edges_path: Path, **kwargs):
    outcomes = []
    summary = None
    for item in publish_merged_paths(
        nodes_path,
        edges_path,
        schema_path=SCHEMA,
        **kwargs,
    ):
        if isinstance(item, PublishSummary):
            summary = item
            break
        outcomes.append(item)
    return outcomes, summary


def test_publish_a1bg_and_quarantines_invalid_gene(tmp_path):
    valid_gene = {
        "id": "silkg:Gene:9606:1",
        "@type": "Gene",
        "symbol": "A1BG",
        "name": "alpha-1-B glycoprotein",
        "tax_id": "NCBITaxon:9606",
        "sources": [{"source_name": "ncbi-gene-info", "bronze_line": 0}],
    }
    invalid_gene = {
        "id": 999,
        "@type": "Gene",
        "sources": [{"source_name": "ncbi-gene-info", "bronze_line": 1}],
    }
    edge = {
        "id": "silkg:ChromosomeHasGene:9606:19:1",
        "@type": "ChromosomeHasGene",
        "subject": "silkg:Chromosome:9606:19",
        "predicate": "silkg:HAS_GENE",
        "object": "silkg:Gene:9606:1",
        "map_location": "19q13.43",
        "sources": [{"source_name": "ncbi-gene-info", "bronze_line": 0}],
    }

    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    _write_jsonl(nodes_path, [valid_gene, invalid_gene])
    _write_jsonl(edges_path, [edge])

    outcomes, summary = _collect(nodes_path, edges_path)

    assert summary is not None
    assert summary.node_count == 1
    assert summary.edge_count == 1
    assert summary.quarantine_node_count == 1
    assert summary.quarantine_edge_count == 0

    nodes = [o for o in outcomes if o.kind == "node" and o.accepted]
    q_nodes = [o for o in outcomes if o.kind == "node" and not o.accepted]
    edges = [o for o in outcomes if o.kind == "edge" and o.accepted]
    assert nodes[0].record["id"] == "silkg:Gene:9606:1"
    assert "sources" not in nodes[0].record
    assert edges[0].record["predicate"] == "silkg:HAS_GENE"
    assert q_nodes[0].line_number == 1
    assert q_nodes[0].errors


def test_publish_yields_excluded_edge_as_accepted(tmp_path):
    gene = {
        "id": "silkg:Gene:9606:1",
        "@type": "Gene",
        "symbol": "A1BG",
        "tax_id": "NCBITaxon:9606",
    }
    kept_edge = {
        "id": "silkg:ChromosomeHasGene:9606:19:1",
        "@type": "ChromosomeHasGene",
        "subject": "silkg:Chromosome:9606:19",
        "predicate": "silkg:HAS_GENE",
        "object": "silkg:Gene:9606:1",
    }
    excluded_edge = {
        "id": "silkg:GeneHasDbXref:9606:1:HGNC:5",
        "@type": "GeneHasDbXref",
        "subject": "silkg:Gene:9606:1",
        "predicate": "silkg:SAME_AS",
        "object": "HGNC:5",
    }

    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    _write_jsonl(nodes_path, [gene])
    _write_jsonl(edges_path, [kept_edge, excluded_edge])

    outcomes, summary = _collect(
        nodes_path,
        edges_path,
        exclude_edge_types=frozenset({"GeneHasDbXref"}),
    )

    assert summary is not None
    assert summary.input_edge_count == 2
    assert summary.edge_count == 1
    assert summary.quarantine_edge_count == 0

    excluded = [
        o
        for o in outcomes
        if o.kind == "edge" and o.record.get("@type") == "GeneHasDbXref"
    ]
    assert len(excluded) == 1
    assert excluded[0].accepted
    assert excluded[0].errors == []
