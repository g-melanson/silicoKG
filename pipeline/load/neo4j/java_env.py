"""Resolve JAVA_HOME for neo4j-admin when the system JRE is missing."""

from __future__ import annotations

import os
from pathlib import Path


def _java_home_is_valid(java_home: Path) -> bool:
    return (java_home / "bin" / "java").is_file()


def resolve_java_home(*, neo4j_admin: str | None = None) -> str | None:
    """Return a JAVA_HOME suitable for neo4j-admin, or None if unknown."""
    env_home = os.environ.get("JAVA_HOME")
    if env_home and _java_home_is_valid(Path(env_home)):
        return env_home

    for candidate in _neo4j_desktop_runtime_homes():
        if _java_home_is_valid(candidate):
            return str(candidate)

    if neo4j_admin:
        admin_path = Path(neo4j_admin)
        if admin_path.is_file():
            dbms_root = admin_path.parent.parent
            for relative in ("jre", "../jre", "../../jre"):
                candidate = (dbms_root / relative).resolve()
                if _java_home_is_valid(candidate):
                    return str(candidate)

    neo4j_home = os.environ.get("NEO4J_HOME")
    if neo4j_home:
        candidate = Path(neo4j_home) / "jre"
        if _java_home_is_valid(candidate):
            return str(candidate)

    return None


def _neo4j_desktop_runtime_homes() -> list[Path]:
    cache_root = (
        Path.home()
        / "Library/Application Support/neo4j-desktop/Application/Cache/runtime"
    )
    if not cache_root.is_dir():
        return []

    homes: list[Path] = []
    for runtime_dir in sorted(cache_root.iterdir(), reverse=True):
        if not runtime_dir.is_dir():
            continue
        homes.append(runtime_dir / "Contents/Home")
        homes.append(runtime_dir / "Home")
    return homes


def resolve_neo4j_home(*, neo4j_admin: str | None = None) -> str | None:
    """Return NEO4J_HOME for neo4j-admin (dbms root), or None if unknown."""
    env_home = os.environ.get("NEO4J_HOME")
    if env_home:
        candidate = Path(env_home)
        if candidate.is_dir():
            return str(candidate)

    if neo4j_admin:
        admin_path = Path(neo4j_admin)
        if admin_path.is_file() and admin_path.name == "neo4j-admin":
            dbms_root = admin_path.parent.parent
            if (dbms_root / "conf").is_dir() or (dbms_root / "data").is_dir():
                return str(dbms_root)

    return None


def build_subprocess_env(*, neo4j_admin: str | None = None) -> dict[str, str]:
    """Copy the current environment, setting JAVA_HOME and NEO4J_HOME when resolvable."""
    env = os.environ.copy()
    if not env.get("JAVA_HOME"):
        java_home = resolve_java_home(neo4j_admin=neo4j_admin)
        if java_home:
            env["JAVA_HOME"] = java_home

    if not env.get("NEO4J_HOME"):
        neo4j_home = resolve_neo4j_home(neo4j_admin=neo4j_admin)
        if neo4j_home:
            env["NEO4J_HOME"] = neo4j_home

    return env
