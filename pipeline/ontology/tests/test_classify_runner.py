from __future__ import annotations

import json
import shutil
from pathlib import Path

from pipeline.ontology.classify.runner import run
from pipeline.paths import UniversePaths

FIXTURES = Path(__file__).parent / "fixtures"


def test_classify_runner_writes_backup_and_manifest(tmp_path):
    root = tmp_path / "universe"
    paths = UniversePaths(root=root)
    run_id = "classify-test"
    source_name = "obo-so"

    merged_dir = paths.merged_run_dir(run_id)
    merged_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "merged-nodes.jsonl", paths.merged_nodes(run_id))
    shutil.copy(FIXTURES / "merged-edges.jsonl", paths.merged_edges(run_id))

    cache_dir = paths.source_cache_dir(source_name)
    cache_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "minimal-index.yaml", paths.ontology_index_path(source_name))

    exit_code = run(
        run_id=run_id,
        source_name=source_name,
        rules_path=FIXTURES / "classification-rules.yaml",
        source="obo",
        paths=paths,
    )
    assert exit_code == 0

    backup = paths.merged_nodes_pre_classify(run_id)
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == (
        FIXTURES / "merged-nodes.jsonl"
    ).read_text(encoding="utf-8")

    nodes = [
        json.loads(line)
        for line in paths.merged_nodes(run_id).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    parent = next(n for n in nodes if n["id"] == "silkg:Gene:9606:200")
    assert parent["so_types"] == ["SO:0000287"]
    assert parent["so_qualities"] == ["SO:0000806"]

    manifest = json.loads(paths.classify_manifest(run_id).read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_id
    assert manifest["source_name"] == source_name
    assert manifest["annotated_node_count"] == 1
    assert manifest["quarantined_stub_count"] == 0
    assert paths.classify_quarantine_nodes(run_id).is_file()
