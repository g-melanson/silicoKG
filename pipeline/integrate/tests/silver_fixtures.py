"""Builders for silver fragment envelopes in integrate engine tests."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.identity.fragments import build_fragment_envelope

# Shared anchor: A1BG on GRCh38 chr19 contig NC_000019.10
GENE_ID = "silkg:Gene:9606:1"
GENOMIC_SEQUENCE_ID = "silkg:GenomicSequence:9606:NC_000019.10"
MAPS_GENE_EDGE_ID = "silkg:GenomicSequenceMapsGene:9606:NC_000019.10:1"
SILVER_RUN_ID = "test-run"
BRONZE_RECORD = {"gene_id": "1", "tax_id": "9606"}


def gene_fragment(
    *,
    source_name: str = "ncbi-gene-info",
    bronze_line: int = 0,
    **slots: object,
) -> dict:
    return build_fragment_envelope(
        target_class="Gene",
        obj={"id": GENE_ID, "@type": "Gene", **slots},
        source_name=source_name,
        silver_run_id=SILVER_RUN_ID,
        bronze_line=bronze_line,
        bronze_record=BRONZE_RECORD,
    )


def maps_gene_fragment(
    *,
    source_name: str = "ncbi-gene2refseq",
    bronze_line: int = 0,
    start: str = "100",
    end: str = "200",
    status: str = "REVIEWED",
    **extra: object,
) -> dict:
    return build_fragment_envelope(
        target_class="GenomicSequenceMapsGene",
        obj={
            "id": MAPS_GENE_EDGE_ID,
            "@type": "GenomicSequenceMapsGene",
            "subject": GENOMIC_SEQUENCE_ID,
            "predicate": "silkg:MAPS_TO",
            "object": GENE_ID,
            "start": start,
            "end": end,
            "status": status,
            **extra,
        },
        source_name=source_name,
        silver_run_id=SILVER_RUN_ID,
        bronze_line=bronze_line,
        bronze_record=BRONZE_RECORD,
    )


def write_silver(
    tmp_path: Path,
    fragments: list[dict],
    name: str = "fragments.jsonl",
) -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(f) + "\n" for f in fragments), encoding="utf-8")
    return path
