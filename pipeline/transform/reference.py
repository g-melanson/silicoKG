"""Static reference tables used to enrich transform output.

Currently ships the human contig -> chromosome map that backs
``ChromosomeRepresentedBy`` edges (Chromosome -REPRESENTED_BY-> GenomicSequence).
The map is emitted once per run rather than per bronze row.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from pipeline.identity.uris import (
    chromosome_represented_by_id,
    chromosome_uri,
    genomic_sequence_uri,
)
from pipeline.paths import REPO_ROOT

GRCH38_CONTIGS_PATH = REPO_ROOT / "schemas" / "reference" / "grch38-contigs.yaml"


@lru_cache(maxsize=None)
def load_contig_map(path: Path = GRCH38_CONTIGS_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def chromosome_represented_by_fragments(
    path: Path = GRCH38_CONTIGS_PATH,
) -> list[dict]:
    """Build one ChromosomeRepresentedBy edge object per known contig.

    Returns bare edge objects (with ``@type``); callers wrap them in silver
    fragment envelopes.
    """
    data = load_contig_map(path)
    tax_id = str(data["tax_id"])
    fragments: list[dict] = []
    for accession, meta in data["contigs"].items():
        chromosome = str(meta["chromosome"])
        fragments.append(
            {
                "id": chromosome_represented_by_id(tax_id, chromosome, accession),
                "subject": chromosome_uri(tax_id, chromosome),
                "predicate": "silkg:REPRESENTED_BY",
                "object": genomic_sequence_uri(tax_id, accession),
                "@type": "ChromosomeRepresentedBy",
            }
        )
    return fragments
