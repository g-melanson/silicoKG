"""Tests for publish configuration parsing."""

import pytest

from pipeline.publish.config import PublishConfig
from pipeline.publish.projection import DEFAULT_STRIP_SLOTS


def test_from_mapping_defaults():
    config = PublishConfig.from_mapping(None)
    assert config.strip_slots == DEFAULT_STRIP_SLOTS
    assert config.exclude_edge_types == frozenset()


def test_from_mapping_merges_strip_slots_with_defaults():
    config = PublishConfig.from_mapping({"strip_slots": ["custom_slot"]})
    assert config.strip_slots == DEFAULT_STRIP_SLOTS | {"custom_slot"}


def test_from_mapping_parses_exclude_edge_types():
    config = PublishConfig.from_mapping({"exclude_edge_types": ["GeneHasDbXref"]})
    assert config.exclude_edge_types == frozenset({"GeneHasDbXref"})


def test_from_mapping_rejects_invalid_list():
    with pytest.raises(ValueError, match="exclude_edge_types"):
        PublishConfig.from_mapping({"exclude_edge_types": "GeneHasDbXref"})
