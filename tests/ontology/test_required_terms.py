from __future__ import annotations

from pathlib import Path

from pipeline.export.neo4j.label_map import DEFAULT_LABEL_MAP_PATH
from pipeline.ontology.classify.context import DEFAULT_RULES_PATH
from pipeline.ontology.required_terms import collect_required_curie_iris
from pipeline.paths import REPO_ROOT


def test_collect_required_curie_iris_includes_gc_signal_mapping():
    curies = collect_required_curie_iris(
        rules_path=REPO_ROOT / "schemas/ontology/classification-rules.yaml",
        label_map_path=DEFAULT_LABEL_MAP_PATH,
    )
    assert "SO:0000307" in curies
    assert "SO:0001411" in curies
    assert "SO:0000165" in curies


def test_collect_required_curie_iris_from_rules_fixture():
    rules = Path(__file__).parent / "fixtures" / "classification-rules.yaml"
    curies = collect_required_curie_iris(rules_path=rules, label_map_path=Path("/nonexistent"))
    assert curies == frozenset({"SO:0000287"})
