from __future__ import annotations

import json
from pathlib import Path

from pipeline.publish.engine import publish_merged_paths

REPO = Path(__file__).resolve().parents[3]
SCHEMA = REPO / "schemas" / "domain" / "gene-or-gene-product.yaml"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


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

    nodes, edges, q_nodes, q_edges, summary = publish_merged_paths(
        nodes_path,
        edges_path,
        schema_path=SCHEMA,
    )

    assert summary.node_count == 1
    assert summary.edge_count == 1
    assert summary.quarantine_node_count == 1
    assert summary.quarantine_edge_count == 0
    assert nodes[0]["id"] == "silkg:Gene:9606:1"
    assert "sources" not in nodes[0]
    assert edges[0]["predicate"] == "silkg:HAS_GENE"
    assert q_nodes[0]["line_number"] == 1
    assert q_nodes[0]["errors"]
