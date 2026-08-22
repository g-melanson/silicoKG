from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.load.neo4j.engine import (
    discover_node_csvs,
    group_relationships_by_endpoint_labels,
    group_relationships_by_type,
    infer_node_label,
    load_relationship_batch,
    parse_node_csv,
    parse_relationships_csv,
)


class _FakeResult:
    def __init__(self, written: int) -> None:
        self._written = written

    def single(self):
        return {"written": self._written}


class _FakeSession:
    def __init__(self, written: int | None = None) -> None:
        self.queries: list[str] = []
        self.row_batches: list[list[dict]] = []
        self._written = written

    def run(self, query: str, **params):
        self.queries.append(query)
        rows = list(params.get("rows", []))
        self.row_batches.append(rows)
        written = self._written if self._written is not None else len(rows)
        return _FakeResult(written)


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


def test_group_relationships_by_endpoint_labels_splits_mixed_starts():
    rows = [
        {
            "type": "ASSOCIATED_WITH",
            "startId": "silkg:Gene:9606:1",
            "endId": "silkg:Disease:doid:1",
            "properties": {},
        },
        {
            "type": "ASSOCIATED_WITH",
            "startId": "silkg:Protein:9606:P12345",
            "endId": "silkg:Disease:doid:1",
            "properties": {},
        },
    ]

    grouped = group_relationships_by_endpoint_labels(rows)

    assert set(grouped) == {("Gene", "Disease"), ("Protein", "Disease")}
    assert grouped[("Gene", "Disease")][0]["startId"] == "silkg:Gene:9606:1"
    assert grouped[("Protein", "Disease")][0]["startId"] == "silkg:Protein:9606:P12345"


def test_load_relationship_batch_splits_mixed_gene_protein_start_labels():
    rows = (
        {
            "startId": "silkg:Gene:9606:1",
            "endId": "silkg:Disease:doid:1",
            "type": "ASSOCIATED_WITH",
            "properties": {},
        },
        {
            "startId": "silkg:Protein:9606:P12345",
            "endId": "silkg:Disease:doid:1",
            "type": "ASSOCIATED_WITH",
            "properties": {},
        },
    )
    session = _FakeSession()

    written = load_relationship_batch(session, "ASSOCIATED_WITH", rows)

    assert written == 2
    assert len(session.queries) == 2
    assert "MATCH (start:Gene {nodeId: row.startId})" in session.queries[0]
    assert "MATCH (end:Disease {nodeId: row.endId})" in session.queries[0]
    assert "MATCH (start:Protein {nodeId: row.startId})" in session.queries[1]
    assert session.row_batches[0][0]["startId"] == "silkg:Gene:9606:1"
    assert session.row_batches[1][0]["startId"] == "silkg:Protein:9606:P12345"


def test_load_relationship_batch_returns_written_count_not_input_len(caplog):
    rows = (
        {
            "startId": "silkg:Gene:9606:1",
            "endId": "silkg:Disease:doid:1",
            "type": "ASSOCIATED_WITH",
            "properties": {},
        },
        {
            "startId": "silkg:Gene:9606:2",
            "endId": "silkg:Disease:doid:1",
            "type": "ASSOCIATED_WITH",
            "properties": {},
        },
    )
    session = _FakeSession(written=1)

    with caplog.at_level("WARNING"):
        written = load_relationship_batch(session, "ASSOCIATED_WITH", rows)

    assert written == 1
    assert "skipped 1 ASSOCIATED_WITH relationship(s)" in caplog.text
    assert "MATCH wrote 1 of 2 rows" in caplog.text


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
