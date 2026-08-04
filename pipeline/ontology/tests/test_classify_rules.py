from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.ontology.classify.rules import (
    AnnotateAction,
    AnnotateMapAction,
    ClassificationRulesError,
    EdgeMatchWhen,
    NodeMatchWhen,
    PropagateRestrictionsAction,
    load_rules,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_rules_reads_actions_document():
    doc = load_rules(FIXTURES / "classification-rules.yaml")
    assert doc.version == 1
    assert len(doc.rules) == 1
    rule = doc.rules[0]
    assert rule.id == "readthrough-parent-is-fusion-gene"
    assert isinstance(rule.when, EdgeMatchWhen)
    assert rule.when.edge_class == "GeneHasReadthroughParent"
    assert rule.when.role == "object"
    assert isinstance(rule.actions[0], AnnotateAction)
    assert rule.actions[0].value == "SO:0000287"
    assert isinstance(rule.actions[1], PropagateRestrictionsAction)
    assert rule.actions[1].property_map["so:has_quality"] == "so_qualities"


def test_load_rules_rejects_missing_file(tmp_path):
    with pytest.raises(ClassificationRulesError, match="not found"):
        load_rules(tmp_path / "missing.yaml")


def test_load_rules_rejects_bad_role(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
version: 1
rules:
  - id: bad
    when:
      edge:
        class: GeneHasReadthroughParent
        role: parent
    actions:
      - annotate:
          target_entity: Gene
          slot: so_types
          value: SO:0000287
""",
        encoding="utf-8",
    )
    with pytest.raises(ClassificationRulesError, match="role"):
        load_rules(path)


def test_load_rules_rejects_empty_actions(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
version: 1
rules:
  - id: bad
    when:
      edge:
        class: GeneHasReadthroughParent
        role: object
    actions: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ClassificationRulesError, match="actions"):
        load_rules(path)


def test_load_annotate_map_rule():
    doc = load_rules(FIXTURES / "annotate-map-rules.yaml")
    rule = doc.rules[0]
    assert isinstance(rule.when, NodeMatchWhen)
    assert rule.when.type_name == "Gene"
    assert rule.when.slot is None
    assert isinstance(rule.actions[0], AnnotateMapAction)
    assert rule.actions[0].from_slot == "type"
    assert rule.actions[0].value_map["ncRNA"] == "SO:0000655"


def test_load_rules_rejects_empty_annotate_map(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
version: 1
rules:
  - id: bad
    when:
      node:
        "@type": Gene
    actions:
      - annotate_map:
          target_entity: Gene
          slot: so_types
          from_slot: type
          map: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(ClassificationRulesError, match="annotate_map.map"):
        load_rules(path)


def test_when_node_does_not_use_bare_type_as_entity(tmp_path):
    """Bare 'type' is a Gene property slot, not @type entity filter."""
    path = tmp_path / "rules.yaml"
    path.write_text(
        """
version: 1
rules:
  - id: bare-type
    when:
      node:
        type: Gene
        slot: type
        equals: ncRNA
    actions:
      - annotate:
          target_entity: Gene
          slot: so_types
          value: SO:0000655
""",
        encoding="utf-8",
    )
    doc = load_rules(path)
    when = doc.rules[0].when
    assert isinstance(when, NodeMatchWhen)
    assert when.type_name is None
    assert when.slot == "type"
    assert when.equals == "ncRNA"
