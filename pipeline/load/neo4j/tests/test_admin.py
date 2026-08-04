from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.export.neo4j.import_command import build_import_argv
from pipeline.load.neo4j.admin import (
    Neo4jAdminImportConfig,
    build_admin_import_argv,
    import_inputs_from_manifest,
    run_admin_import,
)


def test_build_import_argv_orders_node_labels(tmp_path):
    gene_csv = tmp_path / "Gene.csv"
    chromosome_csv = tmp_path / "Chromosome.csv"
    rel_csv = tmp_path / "relationships.csv"
    gene_csv.write_text("nodeId:ID\n", encoding="utf-8")
    chromosome_csv.write_text("nodeId:ID\n", encoding="utf-8")
    rel_csv.write_text(":START_ID,:END_ID,:TYPE\n", encoding="utf-8")

    argv = build_import_argv(
        node_files={"Gene": gene_csv, "Chromosome": chromosome_csv},
        relationships_csv=rel_csv,
        database="neo4j",
        overwrite=True,
        neo4j_admin="/usr/local/bin/neo4j-admin",
    )

    assert argv[0] == "/usr/local/bin/neo4j-admin"
    assert argv[1:4] == ["database", "import", "full"]
    assert argv[4] == f"--nodes=Chromosome={chromosome_csv}"
    assert argv[5] == f"--nodes=Gene={gene_csv}"
    assert argv[6] == f"--relationships={rel_csv}"
    assert argv[7] == "--overwrite-destination=true"
    assert argv[8] == "neo4j"


def test_import_inputs_from_manifest(tmp_path):
    nodes_dir = tmp_path / "nodes"
    nodes_dir.mkdir()
    gene_csv = nodes_dir / "Gene.csv"
    rel_csv = tmp_path / "relationships.csv"
    gene_csv.write_text("nodeId:ID\n", encoding="utf-8")
    rel_csv.write_text(":START_ID,:END_ID,:TYPE\n", encoding="utf-8")

    manifest = {
        "paths": {
            "nodes_dir": str(nodes_dir),
            "nodes_csv_by_label": {"Gene": str(gene_csv)},
            "relationships_csv": str(rel_csv),
        }
    }

    node_files, relationships_csv = import_inputs_from_manifest(manifest)

    assert node_files == {"Gene": gene_csv}
    assert relationships_csv == rel_csv


def test_run_admin_import_dry_run(tmp_path, capsys):
    nodes_dir = tmp_path / "nodes"
    nodes_dir.mkdir()
    gene_csv = nodes_dir / "Gene.csv"
    rel_csv = tmp_path / "relationships.csv"
    gene_csv.write_text("nodeId:ID\n", encoding="utf-8")
    rel_csv.write_text(":START_ID,:END_ID,:TYPE\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "paths": {
                    "nodes_csv_by_label": {"Gene": str(gene_csv)},
                    "relationships_csv": str(rel_csv),
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = run_admin_import(
        manifest_path,
        config=Neo4jAdminImportConfig(
            neo4j_admin="/opt/neo4j/bin/neo4j-admin",
            dry_run=True,
        ),
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "/opt/neo4j/bin/neo4j-admin" in output
    assert str(gene_csv) in output
    assert str(rel_csv) in output


def test_build_admin_import_argv_requires_existing_files(tmp_path):
    manifest = {
        "paths": {
            "nodes_csv_by_label": {"Gene": str(tmp_path / "missing.csv")},
            "relationships_csv": str(tmp_path / "relationships.csv"),
        }
    }

    with pytest.raises(FileNotFoundError, match="node CSV not found"):
        build_admin_import_argv(manifest, config=Neo4jAdminImportConfig())
