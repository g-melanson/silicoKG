from __future__ import annotations

import csv
import json
from pathlib import Path

from pipeline.export.neo4j.config import Neo4jExportConfig
from pipeline.export.neo4j.engine import export_neo4j_csv

FIXTURES = Path(__file__).parent / "fixtures"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_export_neo4j_csv_flattens_multiline_property_values(tmp_path):
    nodes = [
        {
            "id": "CORUM:1",
            "@type": "ProteinComplex",
            "class_labels": ["silkg:CORUM"],
            "description": "Line one\nLine two",
            "name": "Example complex",
        }
    ]
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    _write_jsonl(nodes_path, nodes)
    _write_jsonl(edges_path, [])

    nodes_csv_dir = tmp_path / "nodes"
    relationships_csv = tmp_path / "relationships.csv"
    summary = export_neo4j_csv(
        nodes_path,
        edges_path,
        nodes_csv_dir=nodes_csv_dir,
        relationships_csv_path=relationships_csv,
        config=Neo4jExportConfig(),
    )

    with (nodes_csv_dir / summary.node_files["ProteinComplex:CORUM"].name).open(
        encoding="utf-8"
    ) as handle:
        rows = list(csv.reader(handle))

    assert rows[1][2] == "Line one Line two"


def test_export_neo4j_csv_writes_nodes_and_relationships(tmp_path):
    nodes = [
        {
            "id": "silkg:Gene:9606:1",
            "@type": "Gene",
            "symbol": "A1BG",
            "synonyms": ["A1BG", "A1B"],
            "tax_id": "NCBITaxon:9606",
        },
        {
            "id": "silkg:Chromosome:9606:19",
            "@type": "Chromosome",
            "tax_id": "NCBITaxon:9606",
        },
    ]
    edges = [
        {
            "id": "silkg:ChromosomeHasGene:9606:19:1",
            "@type": "ChromosomeHasGene",
            "subject": "silkg:Chromosome:9606:19",
            "predicate": "silkg:HAS_GENE",
            "object": "silkg:Gene:9606:1",
            "map_location": "19q13.43",
        },
        {
            "id": "silkg:GeneHasDbXref:9606:1:HGNC:5",
            "@type": "GeneHasDbXref",
            "subject": "silkg:Gene:9606:1",
            "predicate": "silkg:SAME_AS",
            "object": "HGNC:5",
        },
    ]

    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    nodes_csv_dir = tmp_path / "nodes"
    relationships_csv = tmp_path / "relationships.csv"
    _write_jsonl(nodes_path, nodes)
    _write_jsonl(edges_path, edges)

    summary = export_neo4j_csv(
        nodes_path,
        edges_path,
        nodes_csv_dir=nodes_csv_dir,
        relationships_csv_path=relationships_csv,
    )

    assert summary.node_count == 3
    assert summary.dbxref_node_count == 1
    assert summary.relationship_count == 2
    assert {entry.label: entry.count for entry in summary.node_types} == {
        "Chromosome": 1,
        "DbXref": 1,
        "Gene": 1,
    }

    with (nodes_csv_dir / "Gene.csv").open(encoding="utf-8") as handle:
        gene_rows = list(csv.reader(handle))
    assert gene_rows[0] == [
        "nodeId:ID",
        "symbol:string",
        "synonyms:string[]",
        "tax_id:string",
    ]
    assert gene_rows[1][0] == "silkg:Gene:9606:1"

    with (nodes_csv_dir / "Chromosome.csv").open(encoding="utf-8") as handle:
        chromosome_rows = list(csv.reader(handle))
    assert chromosome_rows[0] == ["nodeId:ID", "tax_id:string"]
    assert chromosome_rows[1][0] == "silkg:Chromosome:9606:19"

    with (nodes_csv_dir / "DbXref.csv").open(encoding="utf-8") as handle:
        dbxref_rows = list(csv.reader(handle))
    assert dbxref_rows[0] == ["nodeId:ID", "curie:string"]
    assert dbxref_rows[1] == ["HGNC:5", "HGNC:5"]

    with relationships_csv.open(encoding="utf-8") as handle:
        rel_rows = list(csv.reader(handle))
    assert rel_rows[0][:3] == [":START_ID", ":END_ID", ":TYPE"]
    assert rel_rows[1][:3] == [
        "silkg:Chromosome:9606:19",
        "silkg:Gene:9606:1",
        "HAS_GENE",
    ]
    assert rel_rows[2][:3] == ["silkg:Gene:9606:1", "HGNC:5", "SAME_AS"]


def test_export_neo4j_csv_can_block_dbxref_stubs_and_edges(tmp_path):
    nodes = [
        {
            "id": "silkg:Gene:9606:1",
            "@type": "Gene",
            "symbol": "A1BG",
            "dbxrefs": ["HGNC:5"],
            "tax_id": "NCBITaxon:9606",
        },
        {
            "id": "silkg:Chromosome:9606:19",
            "@type": "Chromosome",
            "tax_id": "NCBITaxon:9606",
        },
    ]
    edges = [
        {
            "id": "silkg:ChromosomeHasGene:9606:19:1",
            "@type": "ChromosomeHasGene",
            "subject": "silkg:Chromosome:9606:19",
            "predicate": "silkg:HAS_GENE",
            "object": "silkg:Gene:9606:1",
        },
        {
            "id": "silkg:GeneHasDbXref:9606:1:HGNC:5",
            "@type": "GeneHasDbXref",
            "subject": "silkg:Gene:9606:1",
            "predicate": "silkg:SAME_AS",
            "object": "HGNC:5",
        },
    ]

    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    nodes_csv_dir = tmp_path / "nodes"
    relationships_csv = tmp_path / "relationships.csv"
    _write_jsonl(nodes_path, nodes)
    _write_jsonl(edges_path, edges)

    config = Neo4jExportConfig.from_mapping(
        {
            "exclude_edge_types": ["GeneHasDbXref"],
            "stub_nodes": False,
            "exclude_node_properties": ["dbxrefs"],
        }
    )
    summary = export_neo4j_csv(
        nodes_path,
        edges_path,
        nodes_csv_dir=nodes_csv_dir,
        relationships_csv_path=relationships_csv,
        config=config,
    )

    assert summary.node_count == 2
    assert summary.dbxref_node_count == 0
    assert summary.relationship_count == 1
    assert summary.skipped_edge_count == 1
    assert set(summary.node_files) == {"Chromosome", "Gene"}
    assert not (nodes_csv_dir / "DbXref.csv").exists()

    with (nodes_csv_dir / "Gene.csv").open(encoding="utf-8") as handle:
        gene_rows = list(csv.reader(handle))
    assert "dbxrefs:string[]" not in gene_rows[0]
    assert len(gene_rows) == 2

    with relationships_csv.open(encoding="utf-8") as handle:
        rel_rows = list(csv.reader(handle))
    assert len(rel_rows) == 2
    assert rel_rows[1][2] == "HAS_GENE"


def test_export_neo4j_csv_clears_nodes_csv_dir(tmp_path):

    nodes_csv_dir = tmp_path / "nodes"
    relationships_csv = tmp_path / "relationships.csv"

    nodes_path = FIXTURES / "nodes_valid.jsonl"
    edges_path = FIXTURES / "edges_valid.jsonl"

    nodes_csv_dir.mkdir(parents=True)
    canary_file = nodes_csv_dir / "run_1_marker.csv"
    canary_file.touch()

    summary = export_neo4j_csv(
        nodes_path,
        edges_path,
        nodes_csv_dir=nodes_csv_dir,
        relationships_csv_path=relationships_csv,
        config=Neo4jExportConfig(),
    )

    assert not canary_file.exists()
