from __future__ import annotations

import json
import shutil
from pathlib import Path

from pipeline.ontology.classify.engine import classify_merged_paths
from pipeline.ontology.classify.rules import load_rules
from pipeline.ontology.index import load_index

FIXTURES = Path(__file__).parent / "fixtures"


def _copy_fixtures(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    nodes = tmp_path / "nodes.jsonl"
    edges = tmp_path / "edges.jsonl"
    index = tmp_path / "index.yaml"
    rules = tmp_path / "rules.yaml"
    shutil.copy(FIXTURES / "merged-nodes.jsonl", nodes)
    shutil.copy(FIXTURES / "merged-edges.jsonl", edges)
    shutil.copy(FIXTURES / "minimal-index.yaml", index)
    shutil.copy(FIXTURES / "classification-rules.yaml", rules)
    return nodes, edges, index, rules


def test_classify_annotates_readthrough_parent(tmp_path):
    nodes_path, edges_path, index_path, rules_path = _copy_fixtures(tmp_path)
    nodes, quarantine, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=index_path,
        rules_path=rules_path,
    )

    by_id = {node["id"]: node for node in nodes}
    parent = by_id["silkg:Gene:9606:200"]
    child = by_id["silkg:Gene:9606:100"]

    assert parent["so_types"] == ["SO:0000287"]
    assert parent["so_qualities"] == ["SO:0000806"]
    assert "so_types" not in child
    assert "so_qualities" not in child
    assert quarantine == []
    assert summary.annotated_node_count == 1
    assert summary.rule_match_counts["readthrough-parent-is-fusion-gene"] == 1


def test_classify_dedupes_on_rerun(tmp_path):
    nodes_path, edges_path, index_path, rules_path = _copy_fixtures(tmp_path)
    index = load_index(index_path)
    rules = load_rules(rules_path)

    nodes, _, _ = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=index_path,
        rules_path=rules_path,
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
        index_path=index_path,
        rules_path=rules_path,
        index=index,
        rules=rules,
    )
    parent = next(n for n in nodes_again if n["id"] == "silkg:Gene:9606:200")
    assert parent["so_types"] == ["SO:0000287"]
    assert parent["so_qualities"] == ["SO:0000806"]
    assert summary.annotated_node_count == 0
