"""Build neo4j-admin database import full command arguments."""

from __future__ import annotations

import os
import shlex
from pathlib import Path


def build_import_argv(
    *,
    node_files: dict[str, Path | str],
    relationships_csv: Path | str,
    database: str = "neo4j",
    overwrite: bool = False,
    neo4j_admin: str | None = None,
) -> list[str]:
    admin = resolve_neo4j_admin(neo4j_admin)
    argv = [admin, "database", "import", "full"]
    for label, path in sorted(node_files.items()):
        argv.append(f"--nodes={label}={path}")
    argv.append(f"--relationships={relationships_csv}")
    if overwrite:
        argv.append("--overwrite-destination=true")
    argv.append(database)
    return argv


def format_import_command(argv: list[str]) -> str:
    return shlex.join(argv)


def resolve_neo4j_admin(neo4j_admin: str | None = None) -> str:
    if neo4j_admin:
        return neo4j_admin

    env_admin = os.environ.get("NEO4J_ADMIN")
    if env_admin:
        return env_admin

    neo4j_home = os.environ.get("NEO4J_HOME")
    if neo4j_home:
        candidate = Path(neo4j_home) / "bin" / "neo4j-admin"
        if candidate.exists():
            return str(candidate)

    return "neo4j-admin"


def validate_import_inputs(
    *,
    node_files: dict[str, Path | str],
    relationships_csv: Path | str,
) -> None:
    for label, path in node_files.items():
        node_path = Path(path)
        if not node_path.exists():
            raise FileNotFoundError(f"node CSV not found for {label}: {node_path}")

    rel_path = Path(relationships_csv)
    if not rel_path.exists():
        raise FileNotFoundError(f"relationship CSV not found: {rel_path}")
