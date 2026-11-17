import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.integrate.context import IntegrateContext
from pipeline.integrate.engine import integrate_silver_paths
from pipeline.integrate.priorities import load_priorities
from pipeline.io.jsonl import JsonlWriter


def run(
    run_id: str,
    source_names: list[str],
    priorities_path: Path | None = None,
) -> int:
    ctx = IntegrateContext(run_id=run_id, source_names=tuple(source_names))
    priorities = load_priorities(priorities_path)

    fragment_paths = [
        ctx.paths.silver_fragments(source_name, run_id) for source_name in source_names
    ]
    for path in fragment_paths:
        if not path.exists():
            raise FileNotFoundError(f"silver fragments not found: {path}")

    ctx.paths.merged_run_dir(run_id).mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)

    nodes, edges, quarantine, summary = integrate_silver_paths(fragment_paths, priorities)

    with JsonlWriter(ctx.paths.merged_nodes(run_id)) as node_file:
        node_file.writelines_objs(nodes)

    with JsonlWriter(ctx.paths.merged_edges(run_id)) as edge_file:
        edge_file.writelines_objs(edges)

    with JsonlWriter(ctx.paths.merged_quarantine(run_id)) as q_file:
        q_file.writelines_objs(quarantine)

    resolution_report = {
        "redirects": [],
        "merged_nodes": summary.node_count,
        "merged_edges": summary.edge_count,
        "quarantined": summary.quarantine_count,
        "edge_payload_conflicts": summary.edge_payload_conflicts,
        "edge_payload_conflict_samples": summary.edge_payload_conflict_samples,
    }
    ctx.paths.merged_resolution_report(run_id).write_text(
        json.dumps(resolution_report, indent=2),
        encoding="utf-8",
    )

    finished_at = datetime.now(timezone.utc)
    duration_seconds = (finished_at - started_at).total_seconds()
    ctx.paths.merged_manifest(run_id).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": duration_seconds,
                "stage": "integrate",
                "tier": "merged",
                "sources": list(source_names),
                "priorities_path": str(priorities_path or "schemas/integrate-priorities.yaml"),
                "drift": {
                    "fragment_count": summary.fragment_count,
                    "node_count": summary.node_count,
                    "edge_count": summary.edge_count,
                    "quarantine_count": summary.quarantine_count,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if summary.accepted_count == 0:
        return 1
    return 0
