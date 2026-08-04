"""Orchestrate merged-node classification artifacts."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pipeline.ontology.classify.context import (
    DEFAULT_RULES_PATH,
    DEFAULT_SOURCE_NAME,
    ClassifyContext,
)
from pipeline.ontology.classify.engine import classify_merged_paths
from pipeline.paths import DEFAULT_PATHS, REPO_ROOT, UniversePaths

log = logging.getLogger(__name__)


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def run(
    run_id: str,
    *,
    source_name: str = DEFAULT_SOURCE_NAME,
    rules_path: Path | str | None = None,
    source: str | None = None,
    paths: UniversePaths = DEFAULT_PATHS,
) -> int:
    resolved_rules = _resolve_path(Path(rules_path) if rules_path else DEFAULT_RULES_PATH)
    ctx = ClassifyContext(
        run_id=run_id,
        source_name=source_name,
        rules_path=resolved_rules,
        source=source,
        paths=paths,
    )

    nodes_path = ctx.paths.merged_nodes(run_id)
    edges_path = ctx.paths.merged_edges(run_id)
    for path in (nodes_path, edges_path):
        if not path.exists():
            raise FileNotFoundError(f"merged artifact not found: {path}")

    index_path = ctx.paths.ontology_index_path(ctx.source_name)
    if not index_path.exists():
        raise FileNotFoundError(f"ontology index not found: {index_path}")

    backup_path = ctx.paths.merged_nodes_pre_classify(run_id)
    started_at = datetime.now(timezone.utc)
    shutil.copy2(nodes_path, backup_path)

    nodes, quarantine_stubs, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=index_path,
        rules_path=ctx.rules_path,
    )

    with nodes_path.open("w", encoding="utf-8") as node_file:
        for node in nodes:
            node_file.write(json.dumps(node) + "\n")

    quarantine_path = ctx.paths.classify_quarantine_nodes(run_id)
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    with quarantine_path.open("w", encoding="utf-8") as q_file:
        for stub in quarantine_stubs:
            q_file.write(json.dumps(stub) + "\n")

    finished_at = datetime.now(timezone.utc)
    ctx.paths.classify_manifest(run_id).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "source": ctx.source,
                "source_name": ctx.source_name,
                "rules_path": str(ctx.rules_path),
                "index_path": summary.index_path,
                "index_hash": summary.index_hash,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "stage": "classify",
                "tier": "merged",
                "backup_path": str(backup_path),
                "rule_match_counts": summary.rule_match_counts,
                "annotated_node_count": summary.annotated_node_count,
                "quarantined_stub_count": summary.quarantined_stub_count,
                "quarantined_missing_endpoints": summary.quarantined_missing_endpoints,
                "missing_filler_warnings": summary.missing_filler_warnings,
                "unmapped_slot_value_count": summary.unmapped_slot_value_count,
                "unmapped_slot_values": summary.unmapped_slot_values,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log.info(
        "classify complete for %s: annotated=%d quarantined=%d",
        run_id,
        summary.annotated_node_count,
        summary.quarantined_stub_count,
    )
    return 0
