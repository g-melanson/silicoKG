from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipeline.load.neo4j.java_env import build_subprocess_env, resolve_java_home, resolve_neo4j_home


def test_resolve_java_home_prefers_env(tmp_path, monkeypatch):
    java_home = tmp_path / "jdk"
    (java_home / "bin").mkdir(parents=True)
    (java_home / "bin/java").write_text("", encoding="utf-8")
    monkeypatch.setenv("JAVA_HOME", str(java_home))

    assert resolve_java_home() == str(java_home)


def test_resolve_java_home_from_neo4j_desktop_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv("JAVA_HOME", raising=False)

    cache_root = (
        tmp_path
        / "Library/Application Support/neo4j-desktop/Application/Cache/runtime"
    )
    runtime = cache_root / "zulu21.50.19-ca-jre21.0.11-macosx_aarch64"
    java_home = runtime / "Contents/Home"
    (java_home / "bin").mkdir(parents=True)
    (java_home / "bin/java").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "pipeline.load.neo4j.java_env.Path.home",
        lambda: tmp_path,
    )

    assert resolve_java_home() == str(java_home)


def test_build_subprocess_env_sets_java_home_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.delenv("NEO4J_HOME", raising=False)

    cache_root = (
        tmp_path
        / "Library/Application Support/neo4j-desktop/Application/Cache/runtime"
    )
    runtime = cache_root / "zulu21"
    java_home = runtime / "Contents/Home"
    (java_home / "bin").mkdir(parents=True)
    (java_home / "bin/java").write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "pipeline.load.neo4j.java_env.Path.home",
        lambda: tmp_path,
    )

    env = build_subprocess_env()
    assert env["JAVA_HOME"] == str(java_home)


def test_resolve_neo4j_home_from_admin_path(tmp_path, monkeypatch):
    monkeypatch.delenv("NEO4J_HOME", raising=False)

    dbms_root = tmp_path / "dbms-abc"
    (dbms_root / "bin").mkdir(parents=True)
    (dbms_root / "conf").mkdir()
    admin = dbms_root / "bin" / "neo4j-admin"
    admin.write_text("", encoding="utf-8")

    assert resolve_neo4j_home(neo4j_admin=str(admin)) == str(dbms_root)


def test_build_subprocess_env_sets_neo4j_home_from_admin_path(tmp_path, monkeypatch):
    monkeypatch.delenv("NEO4J_HOME", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)

    dbms_root = tmp_path / "dbms-abc"
    (dbms_root / "bin").mkdir(parents=True)
    (dbms_root / "data").mkdir()
    admin = dbms_root / "bin" / "neo4j-admin"
    admin.write_text("", encoding="utf-8")

    env = build_subprocess_env(neo4j_admin=str(admin))
    assert env["NEO4J_HOME"] == str(dbms_root)
