from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.load.neo4j.engine import (
    discover_node_csvs,
    group_relationships_by_type,
    infer_node_label,
    parse_node_csv,
    parse_relationships_csv,
)


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def test_parse_node_csv_reads_properties_and_arrays(tmp_path):
    path = tmp_path / "Gene.csv"
    _write_csv(
        path,
        [
            ["nodeId:ID", "symbol:string", "synonyms:string[]", "tax_id:string"],
            ["silkg:Gene:9606:1", "A1BG", "A1BG;A1B", "NCBITaxon:9606"],
        ],
    )

    label, rows = parse_node_csv(path)

    assert label == "Gene"
    assert rows == [
        {
            "nodeId": "silkg:Gene:9606:1",
            "properties": {
                "symbol": "A1BG",
                "synonyms": ["A1BG", "A1B"],
                "tax_id": "NCBITaxon:9606",
            },
        }
    ]


def test_parse_relationships_csv_reads_type_and_properties(tmp_path):
    path = tmp_path / "relationships.csv"
    _write_csv(
        path,
        [
            [":START_ID", ":END_ID", ":TYPE", "map_location:string"],
            [
                "silkg:Chromosome:9606:19",
                "silkg:Gene:9606:1",
                "HAS_GENE",
                "19q13.43",
            ],
        ],
    )

    rows = parse_relationships_csv(path)

    assert rows == [
        {
            "startId": "silkg:Chromosome:9606:19",
            "endId": "silkg:Gene:9606:1",
            "type": "HAS_GENE",
            "properties": {"map_location": "19q13.43"},
        }
    ]


def test_discover_node_csvs_uses_stem_as_label(tmp_path):
    nodes_dir = tmp_path / "nodes"
    _write_csv(
        nodes_dir / "Gene.csv",
        [["nodeId:ID", "symbol:string"], ["silkg:Gene:9606:1", "A1BG"]],
    )
    _write_csv(
        nodes_dir / "Chromosome.csv",
        [["nodeId:ID", "tax_id:string"], ["silkg:Chromosome:9606:19", "NCBITaxon:9606"]],
    )

    node_files = discover_node_csvs(nodes_dir)

    assert set(node_files) == {"Gene", "Chromosome"}


def test_group_relationships_by_type():
    rows = [
        {"type": "HAS_GENE", "startId": "a", "endId": "b", "properties": {}},
        {"type": "SAME_AS", "startId": "a", "endId": "c", "properties": {}},
        {"type": "HAS_GENE", "startId": "d", "endId": "e", "properties": {}},
    ]

    grouped = group_relationships_by_type(rows)

    assert set(grouped) == {"HAS_GENE", "SAME_AS"}
    assert len(grouped["HAS_GENE"]) == 2


def test_parse_node_csv_rejects_invalid_label(tmp_path):
    path = tmp_path / "bad-label.csv"
    _write_csv(path, [["nodeId:ID"], ["silkg:Gene:9606:1"]])

    with pytest.raises(ValueError, match="invalid Neo4j label"):
        parse_node_csv(path)


@pytest.mark.parametrize(
    ("node_id", "label"),
    [
        ("silkg:Gene:9606:1", "Gene"),
        ("silkg:MeSHDescriptor:mesh:D000209", "MeSHDescriptor"),
        ("silkg:Chromosome:9606:19", "Chromosome"),
        ("http://example.org/node", None),
        ("silkg:bad label:1", None),
    ],
)
def test_infer_node_label(node_id: str, label: str | None):
    assert infer_node_label(node_id) == label
