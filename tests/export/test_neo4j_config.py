import json

import pytest

from pipeline.export.neo4j.config import Neo4jExportConfig


def test_from_mapping_defaults():
    config = Neo4jExportConfig.from_mapping(None)
    assert config.stub_nodes is True
    assert config.exclude_edge_types == frozenset()


def test_from_mapping_parses_export_rules():
    config = Neo4jExportConfig.from_mapping(
        {
            "exclude_edge_types": ["GeneHasDbXref"],
            "stub_nodes": False,
            "exclude_node_properties": ["dbxrefs", "same_as"],
        }
    )
    assert config.exclude_edge_types == frozenset({"GeneHasDbXref"})
    assert config.stub_nodes is False
    assert config.exclude_node_properties == frozenset({"dbxrefs", "same_as"})


def test_from_mapping_rejects_invalid_list():
    with pytest.raises(ValueError, match="exclude_edge_types"):
        Neo4jExportConfig.from_mapping({"exclude_edge_types": "GeneHasDbXref"})


def test_resolve_inherits_exclude_edge_types_from_publish():
    config = Neo4jExportConfig.resolve(
        {"stub_nodes": False},
        publish_raw={"exclude_edge_types": ["GeneHasDbXref"]},
    )
    assert config.exclude_edge_types == frozenset({"GeneHasDbXref"})
    assert config.stub_nodes is False


def test_resolve_inherits_exclude_edge_types_from_gold_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"projection": {"exclude_edge_types": ["GeneHasDbXref"]}},
        ),
        encoding="utf-8",
    )
    config = Neo4jExportConfig.resolve(
        {"stub_nodes": False},
        gold_manifest_path=manifest_path,
    )
    assert config.exclude_edge_types == frozenset({"GeneHasDbXref"})

