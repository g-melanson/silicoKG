import argparse
import os
from pathlib import Path

from pipeline.load.neo4j.admin import Neo4jAdminImportConfig, run_admin_import
from pipeline.load.neo4j.runner import Neo4jConnectionConfig, run as run_bolt
from pipeline.paths import DEFAULT_PATHS


def _connection_from_args(args: argparse.Namespace) -> Neo4jConnectionConfig:
    uri = args.uri or os.environ.get("NEO4J_URI")
    username = args.username or os.environ.get("NEO4J_USERNAME", "neo4j")
    password = args.password or os.environ.get("NEO4J_PASSWORD")

    if not uri:
        raise SystemExit(
            "error: provide --uri or set NEO4J_URI "
            "(for example bolt://localhost:7687)"
        )
    if not password:
        raise SystemExit("error: provide --password or set NEO4J_PASSWORD")

    return Neo4jConnectionConfig(
        uri=uri,
        username=username,
        password=password,
        database=args.database,
    )


def _resolve_manifest_path(args: argparse.Namespace) -> Path | None:
    if args.manifest:
        return args.manifest
    if args.run_id:
        return DEFAULT_PATHS.gold_neo4j_manifest(args.run_id)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load Neo4j bulk-import CSV files via neo4j-admin or Bolt"
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Use neo4j-admin database import full (Neo4j must be stopped)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Pipeline run id; resolves export manifest under universe/{run_id}/",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Export manifest.json from pipeline.export.neo4j",
    )
    parser.add_argument(
        "--nodes-dir",
        type=Path,
        default=None,
        help="Directory containing per-label node CSV files (Bolt mode only)",
    )
    parser.add_argument(
        "--relationships-csv",
        type=Path,
        default=None,
        help="Relationships CSV exported by pipeline.export.neo4j (Bolt mode only)",
    )
    parser.add_argument(
        "--neo4j-admin",
        default=None,
        help="Path to neo4j-admin binary (admin mode; default: NEO4J_ADMIN, NEO4J_HOME/bin, or PATH)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Pass --overwrite-destination=true to neo4j-admin (admin mode)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print neo4j-admin command without executing it (admin mode)",
    )
    parser.add_argument(
        "--uri",
        default=None,
        help="Bolt URI (Bolt mode; default: NEO4J_URI env var)",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Database username (Bolt mode; default: NEO4J_USERNAME env var or neo4j)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Database password (Bolt mode; default: NEO4J_PASSWORD env var)",
    )
    parser.add_argument(
        "--database",
        default="neo4j",
        help="Target database name (default: neo4j)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows per UNWIND batch for Bolt mode (default: 1000)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all nodes and relationships before Bolt load",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars during Bolt CSV read and load",
    )
    args = parser.parse_args()

    manifest_path = _resolve_manifest_path(args)

    if args.admin:
        if manifest_path is None:
            raise SystemExit(
                "error: admin mode requires --manifest or --run-id"
            )
        if not manifest_path.exists():
            raise SystemExit(f"error: manifest not found: {manifest_path}")
        try:
            exit_code = run_admin_import(
                manifest_path,
                config=Neo4jAdminImportConfig(
                    database=args.database,
                    overwrite=args.overwrite,
                    neo4j_admin=args.neo4j_admin,
                    dry_run=args.dry_run,
                ),
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"error: {exc}") from exc
        raise SystemExit(exit_code)

    if manifest_path is None and (
        args.nodes_dir is None or args.relationships_csv is None
    ):
        raise SystemExit(
            "error: provide --manifest or --run-id, or both --nodes-dir and --relationships-csv"
        )

    try:
        connection = _connection_from_args(args)
        exit_code = run_bolt(
            nodes_dir=args.nodes_dir,
            relationships_csv=args.relationships_csv,
            manifest_path=manifest_path,
            connection=connection,
            batch_size=args.batch_size,
            clear=args.clear,
            show_progress=not args.no_progress,
        )
    except (ImportError, FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
