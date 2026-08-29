from __future__ import annotations

import json
from pathlib import Path

from pipeline.paths import UniversePaths
from pipeline.publish.runner import run

REPO = Path(__file__).resolve().parents[3]


def test_run_writes_gold_manifest(tmp_path):
    run_id = "publish-test"
    universe_root = tmp_path / "universe"
    merged_dir = universe_root / run_id / "4-merged"
    merged_dir.mkdir(parents=True)
    gold_dir = universe_root / run_id / "5-gold"

    gene = {
        "id": "silkg:Gene:9606:1",
        "@type": "Gene",
        "symbol": "A1BG",
        "name": "alpha-1-B glycoprotein",
        "tax_id": "NCBITaxon:9606",
        "sources": [{"source_name": "ncbi-gene-info", "bronze_line": 0}],
    }
    (merged_dir / "nodes.jsonl").write_text(json.dumps(gene) + "\n", encoding="utf-8")
    (merged_dir / "edges.jsonl").write_text("", encoding="utf-8")

    schema_path = REPO / "schemas" / "domain" / "gene-or-gene-product.yaml"
    exit_code = run(
        run_id=run_id,
        schema_path=schema_path,
        paths=UniversePaths(root=universe_root),
    )

    assert exit_code == 0
    manifest = json.loads((gold_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stage"] == "publish"
    assert manifest["projection"]["strip_slots"] == sorted(
        ["alternates", "dbxrefs", "same_as", "sources"]
    )
    assert (gold_dir / "nodes.jsonl").exists()

    gold_gene = json.loads((gold_dir / "nodes.jsonl").read_text(encoding="utf-8").strip())
    assert "sources" not in gold_gene


def test_run_excludes_configured_edge_types(tmp_path):
    run_id = "publish-edge-filter"
    universe_root = tmp_path / "universe"
    merged_dir = universe_root / run_id / "4-merged"
    merged_dir.mkdir(parents=True)
    gold_dir = universe_root / run_id / "5-gold"

    gene = {
        "id": "silkg:Gene:9606:1",
        "@type": "Gene",
        "symbol": "A1BG",
        "tax_id": "NCBITaxon:9606",
    }
    kept_edge = {
        "id": "silkg:ChromosomeHasGene:9606:19:1",
        "@type": "ChromosomeHasGene",
        "subject": "silkg:Chromosome:9606:19",
        "predicate": "silkg:HAS_GENE",
        "object": "silkg:Gene:9606:1",
    }
    dropped_edge = {
        "id": "silkg:GeneHasDbXref:9606:1:HGNC:5",
        "@type": "GeneHasDbXref",
        "subject": "silkg:Gene:9606:1",
        "predicate": "silkg:SAME_AS",
        "object": "HGNC:5",
    }
    (merged_dir / "nodes.jsonl").write_text(json.dumps(gene) + "\n", encoding="utf-8")
    (merged_dir / "edges.jsonl").write_text(
        json.dumps(kept_edge) + "\n" + json.dumps(dropped_edge) + "\n",
        encoding="utf-8",
    )

    schema_path = REPO / "schemas" / "domain" / "gene-or-gene-product.yaml"
    from pipeline.publish.config import PublishConfig

    exit_code = run(
        run_id=run_id,
        schema_path=schema_path,
        config=PublishConfig.from_mapping({"exclude_edge_types": ["GeneHasDbXref"]}),
        paths=UniversePaths(root=universe_root),
    )

    assert exit_code == 0
    manifest = json.loads((gold_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["drift"]["edge_count"] == 1
    assert manifest["projection"]["exclude_edge_types"] == ["GeneHasDbXref"]

    gold_edges = [
        json.loads(line)
        for line in (gold_dir / "edges.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(gold_edges) == 1
    assert gold_edges[0]["@type"] == "ChromosomeHasGene"

    quarantine_edges = [
        json.loads(line)
        for line in (gold_dir / "quarantine" / "edges.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(quarantine_edges) == 1
    assert quarantine_edges[0]["record"]["@type"] == "GeneHasDbXref"
    assert manifest["drift"]["quarantine_edge_count"] == 0
