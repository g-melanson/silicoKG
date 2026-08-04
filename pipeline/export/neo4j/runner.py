import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.export.neo4j.config import Neo4jExportConfig
from pipeline.export.neo4j.context import Neo4jExportContext
from pipeline.export.neo4j.engine import export_neo4j_csv
from pipeline.paths import DEFAULT_PATHS, UniversePaths

from pipeline.export.neo4j.import_command import build_import_argv, format_import_command
def run(
    run_id: str,
    gold_run_id: str | None = None,
    config: Neo4jExportConfig | None = None,
    paths: UniversePaths = DEFAULT_PATHS,
) -> int:
    ctx = Neo4jExportContext(
        run_id=run_id,
        gold_run_id=gold_run_id,
        config=config or Neo4jExportConfig(),
        paths=paths,
    )
    gold_run_id = ctx.effective_gold_run_id
    nodes_path = ctx.paths.gold_nodes(gold_run_id)
    edges_path = ctx.paths.gold_edges(gold_run_id)
    for path in (nodes_path, edges_path):
        if not path.exists():
            raise FileNotFoundError(f"gold artifact not found: {path}")

    nodes_csv_dir = ctx.paths.gold_neo4j_nodes_dir(run_id)
    relationships_csv_path = ctx.paths.gold_neo4j_relationships_csv(run_id)

    started_at = datetime.now(timezone.utc)
    summary = export_neo4j_csv(
        nodes_path,
        edges_path,
        nodes_csv_dir=nodes_csv_dir,
        relationships_csv_path=relationships_csv_path,
        config=ctx.config,
    )
    finished_at = datetime.now(timezone.utc)

    node_files = {
        label: str(path) for label, path in summary.node_files.items()
    }
    ctx.paths.gold_neo4j_manifest(run_id).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "gold_run_id": gold_run_id,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "format": "neo4j-admin-csv",
                "config": {
                    "exclude_edge_types": sorted(ctx.config.exclude_edge_types),
                    "stub_nodes": ctx.config.stub_nodes,
                    "stub_labels": sorted(ctx.config.stub_labels),
                    "exclude_node_properties": sorted(
                        ctx.config.exclude_node_properties
                    ),
                    "label_map": str(ctx.config.label_map_path),
                },
                "paths": {
                    "nodes_dir": str(nodes_csv_dir),
                    "nodes_csv_by_label": node_files,
                    "relationships_csv": str(relationships_csv_path),
                },
                "import_command": format_import_command(
                    build_import_argv(
                        node_files=summary.node_files,
                        relationships_csv=relationships_csv_path,
                    )
                ),
                "counts": {
                    "node_count": summary.node_count,
                    "node_count_by_label": {
                        entry.label: entry.count for entry in summary.node_types
                    },
                    "dbxref_node_count": summary.dbxref_node_count,
                    "relationship_count": summary.relationship_count,
                    "skipped_edge_count": summary.skipped_edge_count,
                },
                "schema": {
                    "node_property_keys_by_label": summary.node_property_keys_by_label,
                    "relationship_property_keys": summary.relationship_property_keys,
                    "array_delimiter": ";",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0
