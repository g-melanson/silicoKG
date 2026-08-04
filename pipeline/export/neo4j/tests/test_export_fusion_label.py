from __future__ import annotations

import csv
import json
from pathlib import Path

from pipeline.export.neo4j.config import Neo4jExportConfig
from pipeline.export.neo4j.engine import export_neo4j_csv
from pipeline.paths import REPO_ROOT


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_export_partitions_fusion_label_from_so_qualities(tmp_path):
    nodes = [
        {
            "id": "silkg:Gene:9606:1",
            "@type": "Gene",
            "symbol": "A1BG",
            "tax_id": "NCBITaxon:9606",
        },
        {
            "id": "silkg:Gene:9606:2",
            "@type": "Gene",
            "symbol": "FUSPARENT",
            "tax_id": "NCBITaxon:9606",
            "so_types": ["SO:0000287"],
            "so_qualities": ["SO:0000806"],
        },
    ]
    edges = [
        {
            "id": "silkg:GeneHasReadthroughParent:9606:3:2",
            "@type": "GeneHasReadthroughParent",
            "subject": "silkg:Gene:9606:3",
            "predicate": "silkg:READTHROUGH_PARENT",
            "object": "silkg:Gene:9606:2",
        }
    ]

    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    nodes_csv_dir = tmp_path / "nodes"
    relationships_csv = tmp_path / "relationships.csv"
    _write_jsonl(nodes_path, nodes)
    _write_jsonl(edges_path, edges)

    config = Neo4jExportConfig.from_mapping(
        {
            "stub_nodes": False,
            "label_map": str(REPO_ROOT / "schemas/ontology/so-label-map.yaml"),
        }
    )
    summary = export_neo4j_csv(
        nodes_path,
        edges_path,
        nodes_csv_dir=nodes_csv_dir,
        relationships_csv_path=relationships_csv,
        config=config,
    )

    assert set(summary.node_files) == {"Gene", "Gene:Fusion"}
    assert (nodes_csv_dir / "Gene.csv").exists()
    assert (nodes_csv_dir / "Gene__Fusion.csv").exists()

    with (nodes_csv_dir / "Gene__Fusion.csv").open(encoding="utf-8") as handle:
        fusion_rows = list(csv.reader(handle))
    assert fusion_rows[0][0] == "nodeId:ID"
    assert "so_types:string[]" in fusion_rows[0]
    assert "so_qualities:string[]" in fusion_rows[0]
    assert fusion_rows[1][0] == "silkg:Gene:9606:2"
    # Labels are applied via --nodes=Gene:Fusion=..., not the CSV ID header.
    assert summary.node_files["Gene:Fusion"].name == "Gene__Fusion.csv"

    with (nodes_csv_dir / "Gene.csv").open(encoding="utf-8") as handle:
        gene_rows = list(csv.reader(handle))
    assert gene_rows[0][0] == "nodeId:ID"
    assert gene_rows[1][0] == "silkg:Gene:9606:1"
