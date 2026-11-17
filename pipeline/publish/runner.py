import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.io.jsonl import JsonlWriter
from pipeline.paths import DEFAULT_PATHS, REPO_ROOT, UniversePaths
from pipeline.publish.config import PublishConfig
from pipeline.publish.context import PublishContext
from pipeline.publish.engine import (
    PublishOutcome,
    PublishSummary,
    publish_merged_paths,
)

PROJECTION_VERSION = "1"
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas/domain/gene-or-gene-product.yaml"


def _quarantine_line(outcome: PublishOutcome) -> dict:
    return {
        "line_number": outcome.line_number,
        "record": outcome.record,
        "errors": outcome.errors,
    }


def _write_publish_stream(
    ctx: PublishContext,
    *,
    nodes_path: Path,
    edges_path: Path,
    exclude_edge_types: frozenset[str],
) -> PublishSummary:
    summary = PublishSummary()
    run_id = ctx.run_id
    with (
        JsonlWriter(ctx.paths.gold_nodes(run_id)) as nodes_out,
        JsonlWriter(ctx.paths.gold_edges(run_id)) as edges_out,
        JsonlWriter(ctx.paths.gold_quarantine_nodes(run_id)) as q_nodes_out,
        JsonlWriter(ctx.paths.gold_quarantine_edges(run_id)) as q_edges_out,
    ):
        for outcome in publish_merged_paths(
            nodes_path,
            edges_path,
            schema_path=ctx.schema_path,
            strip_slots=ctx.strip_slots,
            exclude_edge_types=exclude_edge_types,
        ):
            if isinstance(outcome, PublishSummary):
                summary = outcome
                continue
            if outcome.kind == "node":
                if outcome.accepted:
                    nodes_out.write(outcome.record)
                else:
                    q_nodes_out.write(_quarantine_line(outcome))
                continue
            if (
                outcome.accepted
                and outcome.record.get("@type") not in exclude_edge_types
            ):
                edges_out.write(outcome.record)
            else:
                q_edges_out.write(_quarantine_line(outcome))

    return summary


def run(
    run_id: str,
    merged_run_id: str | None = None,
    schema_path: Path | None = None,
    config: PublishConfig | None = None,
    paths: UniversePaths = DEFAULT_PATHS,
) -> int:
    publish_config = config or PublishConfig()

    ctx = PublishContext(
        run_id=run_id,
        merged_run_id=merged_run_id,
        schema_path=schema_path or DEFAULT_SCHEMA_PATH,
        strip_slots=publish_config.strip_slots,
        paths=paths,
    )

    merged_run_id = ctx.effective_merged_run_id
    nodes_path = ctx.paths.merged_nodes(merged_run_id)
    edges_path = ctx.paths.merged_edges(merged_run_id)
    for path in (nodes_path, edges_path):
        if not path.exists():
            raise FileNotFoundError(f"merged artifact not found: {path}")

    ctx.paths.gold_run_dir(run_id).mkdir(parents=True, exist_ok=True)
    ctx.paths.gold_quarantine_dir(run_id).mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)

    summary = _write_publish_stream(
        ctx,
        nodes_path=nodes_path,
        edges_path=edges_path,
        exclude_edge_types=publish_config.exclude_edge_types,
    )

    finished_at = datetime.now(timezone.utc)
    ctx.paths.gold_manifest(run_id).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "merged_run_id": merged_run_id,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "stage": "publish",
                "tier": "gold",
                "projection": {
                    "version": PROJECTION_VERSION,
                    "strip_slots": sorted(ctx.strip_slots),
                    "exclude_edge_types": sorted(publish_config.exclude_edge_types),
                    "schema_path": str(ctx.schema_path),
                    "validate_order": "strip_then_validate",
                },
                "drift": {
                    "input_node_count": summary.input_node_count,
                    "input_edge_count": summary.input_edge_count,
                    "node_count": summary.node_count,
                    "edge_count": summary.edge_count,
                    "quarantine_node_count": summary.quarantine_node_count,
                    "quarantine_edge_count": summary.quarantine_edge_count,
                    "error_counts": summary.error_counts,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if summary.accepted_count == 0:
        return 1
    return 0
