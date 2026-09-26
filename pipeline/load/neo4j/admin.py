"""Run neo4j-admin database import full from export manifest CSV."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.export.neo4j.import_command import (
    build_import_argv,
    format_import_command,
    validate_import_inputs,
)
from pipeline.load.neo4j.java_env import build_subprocess_env, resolve_java_home, resolve_neo4j_home


@dataclass(frozen=True)
class Neo4jAdminImportConfig:
    database: str = "neo4j"
    overwrite: bool = False
    neo4j_admin: str | None = None
    dry_run: bool = False


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be a mapping")
    return manifest


def import_inputs_from_manifest(
    manifest: dict[str, Any],
) -> tuple[dict[str, Path], Path]:
    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("manifest must include a paths mapping")

    nodes_csv_by_label = paths.get("nodes_csv_by_label")
    if not isinstance(nodes_csv_by_label, dict) or not nodes_csv_by_label:
        raise ValueError("manifest.paths.nodes_csv_by_label must be a non-empty mapping")

    relationships_csv = paths.get("relationships_csv")
    if not relationships_csv:
        raise ValueError("manifest.paths.relationships_csv is required")

    node_files = {label: Path(path) for label, path in nodes_csv_by_label.items()}
    return node_files, Path(relationships_csv)


def build_admin_import_argv(
    manifest: dict[str, Any],
    *,
    config: Neo4jAdminImportConfig,
) -> list[str]:
    node_files, relationships_csv = import_inputs_from_manifest(manifest)
    validate_import_inputs(
        node_files=node_files,
        relationships_csv=relationships_csv,
    )
    return build_import_argv(
        node_files=node_files,
        relationships_csv=relationships_csv,
        database=config.database,
        overwrite=config.overwrite,
        neo4j_admin=config.neo4j_admin,
    )


def run_admin_import(
    manifest_path: Path,
    *,
    config: Neo4jAdminImportConfig | None = None,
) -> int:
    config = config or Neo4jAdminImportConfig()
    manifest = load_manifest(manifest_path)
    argv = build_admin_import_argv(manifest, config=config)
    command = format_import_command(argv)

    if config.dry_run:
        print(command)
        return 0

    admin_path = Path(argv[0])
    if admin_path.name == "neo4j-admin" and admin_path.parent == Path("."):
        pass
    elif not admin_path.exists():
        raise FileNotFoundError(f"neo4j-admin not found: {admin_path}")

    env = build_subprocess_env(neo4j_admin=str(admin_path))
    java_home = env.get("JAVA_HOME") or resolve_java_home(neo4j_admin=str(admin_path))
    neo4j_home = env.get("NEO4J_HOME") or resolve_neo4j_home(neo4j_admin=str(admin_path))
    _verify_neo4j_admin(str(admin_path), env)

    started_at = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(
            argv,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "neo4j-admin not found on PATH. Install Neo4j locally, set NEO4J_HOME, "
            "set NEO4J_ADMIN to the binary path, or pass --neo4j-admin. "
            "Neo4j must be stopped before running database import full."
        ) from exc

    finished_at = datetime.now(timezone.utc)
    duration_seconds = (finished_at - started_at).total_seconds()
    summary = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": duration_seconds,
        "method": "neo4j-admin-import-full",
        "manifest": str(manifest_path),
        "database": config.database,
        "overwrite": config.overwrite,
        "java_home": java_home,
        "neo4j_home": neo4j_home,
        "command": command,
        "exit_code": completed.returncode,
        "counts": manifest.get("counts", {}),
    }
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        if detail:
            detail_lines = detail.splitlines()
            detail = "\n".join(detail_lines[-20:])
        summary["error"] = (
            "neo4j-admin import failed. Stop the database in Neo4j Desktop before "
            "importing. If you see a Java Runtime error, set JAVA_HOME to a JRE 17+ "
            "or use Neo4j Desktop (silicoKG auto-detects its bundled runtime on macOS)."
        )
        if detail:
            summary["error_detail"] = detail
    if completed.stdout:
        sys.stdout.write(completed.stdout)
        if not completed.stdout.endswith("\n"):
            sys.stdout.write("\n")
    if completed.stderr:
        sys.stderr.write(completed.stderr)
        if not completed.stderr.endswith("\n"):
            sys.stderr.write("\n")
    print(json.dumps(summary, indent=2))
    return completed.returncode


def _verify_neo4j_admin(admin_path: str, env: dict[str, str]) -> None:
    try:
        completed = subprocess.run(
            [admin_path, "version"],
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "neo4j-admin not found on PATH. Install Neo4j locally, set NEO4J_HOME, "
            "set NEO4J_ADMIN to the binary path, or pass --neo4j-admin."
        ) from exc

    if completed.returncode == 0:
        return

    java_home = env.get("JAVA_HOME")
    detail = (completed.stderr or completed.stdout or "").strip()
    raise RuntimeError(
        "neo4j-admin is not runnable (Java missing or misconfigured). "
        f"JAVA_HOME={java_home!r}. "
        f"{detail or 'Run neo4j-admin version manually for details.'}"
    )
