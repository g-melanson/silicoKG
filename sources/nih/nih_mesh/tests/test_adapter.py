from __future__ import annotations

from pathlib import Path

import pytest

from sources.nih.nih_mesh.parse import (
    iter_descriptor_records,
    load_allowlist,
    load_ingested_descriptor_uis,
    matches_allowlist,
    parent_tree,
    parse_descriptor_record,
    tree_hierarchy_edges,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_descriptors.xml"


@pytest.mark.parametrize(
    ("tree", "prefix", "expected"),
    [
        ("D05.500.049", "D05.500", True),
        ("D05.500", "D05.500", True),
        ("D05.875", "D05.500", False),
        ("D05.875", "D05.875", True),
    ],
)
def test_matches_allowlist(tree: str, prefix: str, expected: bool) -> None:
    assert matches_allowlist([tree], [prefix]) is expected


def test_parent_tree() -> None:
    assert parent_tree("D05.500.562.374") == "D05.500.562"
    assert parent_tree("D05") is None


def test_parse_descriptor_record_skips_permuted_terms() -> None:
    import xml.etree.ElementTree as ET

    root = ET.parse(FIXTURE).getroot()
    record_elem = root.find("DescriptorRecord")
    assert record_elem is not None
    record = parse_descriptor_record(record_elem)
    assert record["descriptor_ui"] == "D000001"
    assert record["label"] == "Child Term"
    assert record["scope_note"] == "A child descriptor."
    assert record["synonyms"] == ["Child Term", "Child Synonym"]


def test_fixture_filters_and_emits_edges() -> None:
    allowlist = load_allowlist()
    descriptors: dict[str, dict] = {}
    tree_to_ui: dict[str, str] = {}

    for record in iter_descriptor_records(FIXTURE):
        if not matches_allowlist(record["tree_numbers"], allowlist):
            continue
        descriptors[record["descriptor_ui"]] = record
        for tree_number in record["tree_numbers"]:
            tree_to_ui[tree_number] = record["descriptor_ui"]

    descriptor_rows = [
        {
            "row_kind": "descriptor",
            "descriptor_ui": record["descriptor_ui"],
            "label": record["label"],
            "tree_numbers": record["tree_numbers"],
            "scope_note": record.get("scope_note"),
            "synonyms": record.get("synonyms") or [],
        }
        for record in descriptors.values()
    ]
    edge_rows = [
        edge
        for record in descriptors.values()
        for tree_number in record["tree_numbers"]
        for edge in tree_hierarchy_edges(tree_number, tree_to_ui, descriptors)
    ]

    assert {row["descriptor_ui"] for row in descriptor_rows} == {
        "D000001",
        "D000002",
        "D000004",
    }
    assert len(edge_rows) == 1
    assert edge_rows[0]["subject_id"] == "D000001"
    assert edge_rows[0]["object_id"] == "D000002"


def test_load_ingested_descriptor_uis_matches_fixture_adapter() -> None:
    allowlist = load_allowlist()
    expected = {
        record["descriptor_ui"]
        for record in iter_descriptor_records(FIXTURE)
        if matches_allowlist(record["tree_numbers"], allowlist)
    }
    assert load_ingested_descriptor_uis(FIXTURE) == frozenset(expected)


def test_tree_hierarchy_edges_are_immediate_only() -> None:
    descriptors = {
        "D000001": {"descriptor_ui": "D000001"},
        "D000002": {"descriptor_ui": "D000002"},
        "D000003": {"descriptor_ui": "D000003"},
    }
    tree_to_ui = {
        "D05.500.100": "D000001",
        "D05.500": "D000002",
        "D05": "D000003",
    }
    edges = list(tree_hierarchy_edges("D05.500.100", tree_to_ui, descriptors))
    assert len(edges) == 1
    assert edges[0]["object_id"] == "D000002"
