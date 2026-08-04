from __future__ import annotations

import csv
import json
from pathlib import Path

from pipeline.export.neo4j.runner import run
from pipeline.paths import UniversePaths

REPO = Path(__file__).resolve().parents[4]


def test_run_writes_manifest_and_csv(tmp_path):
    run_id = "neo4j-export-test"
    universe_root = tmp_path / "universe"
    gold_dir = universe_root / run_id / "5-gold"
    export_dir = gold_dir / "export" / "neo4j"
    gold_dir.mkdir(parents=True)

    gene = {
        "id": "silkg:Gene:9606:1",
        "@type": "Gene",
        "symbol": "A1BG",
        "tax_id": "NCBITaxon:9606",
    }
    edge = {
        "id": "silkg:ChromosomeHasGene:9606:19:1",
        "@type": "ChromosomeHasGene",
        "subject": "silkg:Chromosome:9606:19",
        "predicate": "silkg:HAS_GENE",
        "object": "silkg:Gene:9606:1",
    }
    chromosome = {
        "id": "silkg:Chromosome:9606:19",
        "@type": "Chromosome",
        "tax_id": "NCBITaxon:9606",
    }
    (gold_dir / "nodes.jsonl").write_text(
        json.dumps(gene) + "\n" + json.dumps(chromosome) + "\n",
        encoding="utf-8",
    )
    (gold_dir / "edges.jsonl").write_text(json.dumps(edge) + "\n", encoding="utf-8")

    exit_code = run(run_id=run_id, paths=UniversePaths(root=universe_root))

    assert exit_code == 0
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "neo4j-admin-csv"
    assert manifest["counts"]["node_count"] == 2
    assert manifest["paths"]["nodes_csv_by_label"] == {
        "Chromosome": str(export_dir / "nodes" / "Chromosome.csv"),
        "Gene": str(export_dir / "nodes" / "Gene.csv"),
    }
    assert "--nodes=Chromosome=" in manifest["import_command"]
    assert "--nodes=Gene=" in manifest["import_command"]

    with (export_dir / "nodes" / "Gene.csv").open(encoding="utf-8") as handle:
        assert len(list(csv.reader(handle))) == 2
    with (export_dir / "nodes" / "Chromosome.csv").open(encoding="utf-8") as handle:
        assert len(list(csv.reader(handle))) == 2
