import argparse
import json
from pathlib import Path

from pipeline.export.neo4j.config import Neo4jExportConfig
from pipeline.export.neo4j.runner import run
from pipeline.paths import DEFAULT_PATHS
from pipeline.run.loader import PipelineRunConfigError, load_run_config


def _load_config(args: argparse.Namespace) -> Neo4jExportConfig:
    if args.run_config:
        ctx = load_run_config(args.run_config)
        gold_run_id = args.gold_run_id or args.run_id
        return Neo4jExportConfig.resolve(
            ctx.stage_args.get("export_neo4j"),
            publish_raw=ctx.stage_args.get("publish"),
            gold_manifest_path=DEFAULT_PATHS.gold_manifest(gold_run_id),
        )
    if args.config:
        import yaml

        with Path(args.config).open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise PipelineRunConfigError("export config root must be a mapping")
        return Neo4jExportConfig.from_mapping(data)
    gold_run_id = args.gold_run_id or args.run_id
    return Neo4jExportConfig.resolve(
        {
            "exclude_edge_types": args.exclude_edge_type or None,
            "stub_nodes": not args.no_stub_nodes,
            "exclude_node_properties": args.exclude_node_property or None,
        }
        if (args.exclude_edge_type or args.no_stub_nodes or args.exclude_node_property)
        else None,
        gold_manifest_path=DEFAULT_PATHS.gold_manifest(gold_run_id),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export gold tier to Neo4j bulk-import CSV datasets"
    )
    parser.add_argument("--run-id", required=True, help="Pipeline run id")
    parser.add_argument(
        "--gold-run-id",
        default=None,
        help="Run id to read gold tier from (default: same as --run-id)",
    )
    parser.add_argument(
        "--run-config",
        type=Path,
        default=None,
        help="Pipeline run YAML containing an export_neo4j section",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Standalone export_neo4j YAML config",
    )
    parser.add_argument(
        "--exclude-edge-type",
        action="append",
        default=[],
        help="Edge @type to omit from relationships.csv (repeatable)",
    )
    parser.add_argument(
        "--exclude-node-property",
        action="append",
        default=[],
        help="Node property to omit from node CSV files (repeatable)",
    )
    parser.add_argument(
        "--no-stub-nodes",
        action="store_true",
        help="Do not create stub nodes for external edge endpoints",
    )
    args = parser.parse_args()

    try:
        config = _load_config(args)
    except (PipelineRunConfigError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    raise SystemExit(
        run(run_id=args.run_id, gold_run_id=args.gold_run_id, config=config)
    )


if __name__ == "__main__":
    main()
