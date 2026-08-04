import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.load.neo4j.engine import discover_node_csvs, load_csv_files


@dataclass(frozen=True)
class Neo4jConnectionConfig:
    uri: str
    username: str
    password: str
    database: str = "neo4j"


def load_manifest_paths(manifest_path: Path) -> tuple[Path, Path, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("manifest must include a paths mapping")

    nodes_dir = Path(paths["nodes_dir"])
    relationships_csv = Path(paths["relationships_csv"])
    array_delimiter = manifest.get("schema", {}).get("array_delimiter", ";")
    return nodes_dir, relationships_csv, array_delimiter


def run(
    *,
    nodes_dir: Path | None = None,
    relationships_csv: Path | None = None,
    manifest_path: Path | None = None,
    connection: Neo4jConnectionConfig,
    batch_size: int = 1000,
    clear: bool = False,
    array_delimiter: str = ";",
    show_progress: bool = True,
) -> int:
    if manifest_path:
        manifest_nodes_dir, manifest_relationships_csv, manifest_delimiter = (
            load_manifest_paths(manifest_path)
        )
        nodes_dir = nodes_dir or manifest_nodes_dir
        relationships_csv = relationships_csv or manifest_relationships_csv
        if array_delimiter == ";":
            array_delimiter = manifest_delimiter

    if nodes_dir is None or relationships_csv is None:
        raise ValueError(
            "provide --nodes-dir and --relationships-csv, or --manifest"
        )

    node_files = discover_node_csvs(nodes_dir)

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise ImportError(
            "neo4j Python driver is required for live loading. "
            "Install it with: pip install neo4j"
        ) from exc

    started_at = datetime.now(timezone.utc)
    driver = GraphDatabase.driver(
        connection.uri,
        auth=(connection.username, connection.password),
    )
    try:
        driver.verify_connectivity()
        summary = load_csv_files(
            driver,
            node_files=node_files,
            relationships_csv=relationships_csv,
            database=connection.database,
            batch_size=batch_size,
            clear=clear,
            array_delimiter=array_delimiter,
            show_progress=show_progress,
        )
    finally:
        driver.close()

    finished_at = datetime.now(timezone.utc)
    summary_payload = json.dumps(
        {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "uri": connection.uri,
            "database": connection.database,
            "nodes_dir": str(nodes_dir),
            "relationships_csv": str(relationships_csv),
            "cleared_before_load": clear,
            "counts": {
                "node_count": summary.node_count,
                "node_count_by_label": summary.node_count_by_label,
                "relationship_count": summary.relationship_count,
                "relationship_count_by_type": summary.relationship_count_by_type,
            },
        },
        indent=2,
    )
    if show_progress:
        from tqdm import tqdm

        tqdm.write(summary_payload)
    else:
        print(summary_payload)
    return 0
