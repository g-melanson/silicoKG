from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pipeline.ontology.classify.engine import ClassifyError, classify_merged_paths
from pipeline.ontology.classify.rules import load_rules
from pipeline.ontology.index import load_index

FIXTURES = Path(__file__).parent / "fixtures"


def _write_empty_edges(path: Path) -> None:
    path.write_text("", encoding="utf-8")


def test_annotate_map_maps_gene_types(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    shutil.copy(FIXTURES / "annotate-map-nodes.jsonl", nodes_path)
    _write_empty_edges(edges_path)

    nodes, quarantine, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=FIXTURES / "minimal-index.yaml",
        rules_path=FIXTURES / "annotate-map-rules.yaml",
    )

    by_id = {node["id"]: node for node in nodes}
    assert by_id["silkg:Gene:9606:1"]["so_types"] == ["SO:0000655"]
    assert by_id["silkg:Gene:9606:2"]["so_types"] == ["SO:0000274"]
    assert "so_types" not in by_id["silkg:Gene:9606:3"]
    assert "so_types" not in by_id["silkg:Protein:9606:4"]
    assert quarantine == []
    assert summary.annotated_node_count == 2
    assert summary.unmapped_slot_value_count == 1
    assert summary.unmapped_slot_values == ["other"]
    assert summary.rule_match_counts["gene-type-to-so"] == 3


def test_annotate_map_dedupes_on_rerun(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    shutil.copy(FIXTURES / "annotate-map-nodes.jsonl", nodes_path)
    _write_empty_edges(edges_path)
    index = load_index(FIXTURES / "minimal-index.yaml")
    rules = load_rules(FIXTURES / "annotate-map-rules.yaml")

    nodes, _, _ = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=FIXTURES / "minimal-index.yaml",
        rules_path=FIXTURES / "annotate-map-rules.yaml",
        index=index,
        rules=rules,
    )
    nodes_path.write_text(
        "".join(json.dumps(node) + "\n" for node in nodes),
        encoding="utf-8",
    )

    nodes_again, _, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=FIXTURES / "minimal-index.yaml",
        rules_path=FIXTURES / "annotate-map-rules.yaml",
        index=index,
        rules=rules,
    )
    gene = next(n for n in nodes_again if n["id"] == "silkg:Gene:9606:1")
    assert gene["so_types"] == ["SO:0000655"]
    assert summary.annotated_node_count == 0


def test_node_exact_match_slot_equals(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    rules_path = tmp_path / "rules.yaml"
    shutil.copy(FIXTURES / "annotate-map-nodes.jsonl", nodes_path)
    _write_empty_edges(edges_path)
    rules_path.write_text(
        """
version: 1
rules:
  - id: only-ncrna
    when:
      node:
        "@type": Gene
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

    nodes, _, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=FIXTURES / "minimal-index.yaml",
        rules_path=rules_path,
    )
    by_id = {node["id"]: node for node in nodes}
    assert by_id["silkg:Gene:9606:1"]["so_types"] == ["SO:0000655"]
    assert "so_types" not in by_id["silkg:Gene:9606:2"]
    assert summary.annotated_node_count == 1
    assert summary.rule_match_counts["only-ncrna"] == 1


def test_annotate_map_inherits_slot_from_edge_subject(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    shutil.copy(FIXTURES / "inherit-type-nodes.jsonl", nodes_path)
    shutil.copy(FIXTURES / "inherit-type-edges.jsonl", edges_path)

    nodes, _, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=FIXTURES / "minimal-index.yaml",
        rules_path=FIXTURES / "inherit-type-rules.yaml",
    )
    by_id = {node["id"]: node for node in nodes}
    assert by_id["silkg:Transcript:9606:1:NM_1"]["so_types"] == ["SO:0000655"]
    assert by_id["silkg:Transcript:9606:2:NR_2"]["so_types"] == ["SO:0000274"]
    assert "so_types" not in by_id["silkg:Gene:9606:1"]
    assert summary.annotated_node_count == 2


def test_load_annotate_map_from_role():
    from pipeline.ontology.classify.rules import AnnotateMapAction, load_rules

    doc = load_rules(FIXTURES / "inherit-type-rules.yaml")
    action = doc.rules[0].actions[0]
    assert isinstance(action, AnnotateMapAction)
    assert action.from_role == "subject"


def test_annotate_map_preflight_rejects_unknown_curie(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    rules_path = tmp_path / "rules.yaml"
    shutil.copy(FIXTURES / "annotate-map-nodes.jsonl", nodes_path)
    _write_empty_edges(edges_path)
    rules_path.write_text(
        """
version: 1
rules:
  - id: bad-map
    when:
      node:
        "@type": Gene
    actions:
      - annotate_map:
          target_entity: Gene
          slot: so_types
          from_slot: type
          map:
            ncRNA: SO:9999999
""",
        encoding="utf-8",
    )

    with pytest.raises(ClassifyError, match="SO:9999999"):
        classify_merged_paths(
            nodes_path,
            edges_path,
            index_path=FIXTURES / "minimal-index.yaml",
            rules_path=rules_path,
        )


def test_annotate_map_multivalued_from_slot(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    shutil.copy(FIXTURES / "feature-types-nodes.jsonl", nodes_path)
    _write_empty_edges(edges_path)

    nodes, quarantine, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=FIXTURES / "minimal-index.yaml",
        rules_path=FIXTURES / "feature-types-rules.yaml",
    )

    by_id = {node["id"]: node for node in nodes}
    assert by_id["silkg:Gene:9606:1"]["so_types"] == ["SO:0000165", "SO:0000625"]
    assert by_id["silkg:Gene:9606:2"]["so_types"] == ["SO:0000165"]
    assert "so_types" not in by_id["silkg:Gene:9606:3"]
    assert quarantine == []
    assert summary.annotated_node_count == 2
    assert summary.unmapped_slot_value_count == 1
    assert summary.unmapped_slot_values == ["unknown_token"]
    assert summary.rule_match_counts["genomic-region-to-so"] == 2


def test_annotate_map_multivalued_dedupes_same_so_curie(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    rules_path = tmp_path / "rules.yaml"
    nodes_path.write_text(
        json.dumps(
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "type": "biological-region",
                "feature_types": [
                    "DNase_I_hypersensitive_site",
                    "micrococcal_nuclease_hypersensitive_site",
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_empty_edges(edges_path)
    rules_path.write_text(
        """
version: 1
rules:
  - id: hypersensitive-to-so
    when:
      node:
        "@type": Gene
        slot: type
        equals: biological-region
    actions:
      - annotate_map:
          target_entity: Gene
          slot: so_types
          from_slot: feature_types
          map:
            DNase_I_hypersensitive_site: SO:0000685
            micrococcal_nuclease_hypersensitive_site: SO:0000685
""",
        encoding="utf-8",
    )

    index_path = tmp_path / "index.yaml"
    index_path.write_text(
        """
version: 1
source_name: obo-so
input_hash: test
classes:
  SO:0000685:
    label: DNaseIHypersensitiveSite
    parents: []
""",
        encoding="utf-8",
    )

    nodes, _, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=index_path,
        rules_path=rules_path,
    )
    gene = nodes[0]
    assert gene["so_types"] == ["SO:0000685"]
    assert summary.annotated_node_count == 1
