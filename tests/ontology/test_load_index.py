from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.ontology.index import OntologyIndexError, load_index
from pipeline.ontology.adapters import BronzeRowKind, OntologyEdgeRow, OntologyTermRow
from pipeline.ontology.index import compile_index, write_index

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_index_round_trips_fixture():
    index = load_index(FIXTURES / "minimal-index.yaml")
    assert index.version == 1
    assert index.source_name == "obo-so"
    assert "SO:0000287" in index.classes
    assert index.restrictions_index["SO:0000287"][0]["filler"] == "SO:0000806"


def test_load_index_missing_file(tmp_path):
    with pytest.raises(OntologyIndexError, match="not found"):
        load_index(tmp_path / "missing.yaml")

def _sample_rows():
    return [
        OntologyTermRow(
            row_kind=BronzeRowKind("term"),
            term_id="GO:0000002",
            iri="http://purl.obolibrary.org/obo/GO_0000002",
            label="second",
            synonyms=["zeta", "alpha"],
        ),
        OntologyTermRow(
            row_kind=BronzeRowKind("term"),
            term_id="GO:0000001",
            iri="http://purl.obolibrary.org/obo/GO_0000001",
            label="first",
            synonyms=[],
        ),
        OntologyEdgeRow(
            row_kind=BronzeRowKind.edge,
            subject_id="GO:0000001",
            predicate_id="rdfs:subClassOf",
            object_id="GO:0000003",
        ),
        OntologyEdgeRow(
            row_kind=BronzeRowKind.edge,
            subject_id="GO:0000001",
            predicate_id="rdfs:subClassOf",
            object_id="GO:0000002",
        ),
        OntologyEdgeRow(
            row_kind=BronzeRowKind.edge,
            subject_id="GO:0000001",
            predicate_id="RO:0002211",
            object_id="GO:0000003",
        ),
        OntologyEdgeRow(
            row_kind=BronzeRowKind.edge,
            subject_id="GO:0000001",
            predicate_id="RO:0000085",
            object_id="GO:0000002",
        ),
    ]

def test_write_index_is_byte_stable(tmp_path):
    rows = _sample_rows()
    compiled = compile_index(rows, source_name="test", input_hash="abc")
    path_a = tmp_path / "a.yaml"
    path_b = tmp_path / "b.yaml"
    write_index(compiled, path_a)
    write_index(compile_index(rows, source_name="test", input_hash="abc"), path_b)
    assert path_a.read_bytes() == path_b.read_bytes()

def test_write_index_ignores_row_order(tmp_path):
    forward = _sample_rows()
    reverse = list(reversed(forward))
    path_a = tmp_path / "a.yaml"
    path_b = tmp_path / "b.yaml"
    write_index(compile_index(forward, source_name="test", input_hash="abc"), path_a)
    write_index(compile_index(reverse, source_name="test", input_hash="abc"), path_b)
    assert path_a.read_bytes() == path_b.read_bytes()
