from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.ontology.index import OntologyIndexError, load_index

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
