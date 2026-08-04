from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from sources.base import TsvSchemaAdapter
from sources.registry import register


@register
class NCBIGeneRefSeqToUniProtAdapter(TsvSchemaAdapter):
    source = "ncbi-gene-refseq-to-uniprot"
    target_class = "NCBIGeneRefSeqToUniProtRow"
    schema_path = Path(__file__).with_name("ncbi-gene-refseq-to-uniprot.schema.yaml")
    url = "data/ncbi/gene_refseq_uniprotkb_collab"
    ingest_required_fields = ("refseq_accession", "uniprot_accession")

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if reader.fieldnames:
                reader.fieldnames = [
                    name.lstrip(self.header_prefix) for name in reader.fieldnames
                ]
            for row in reader:
                if row.get("NCBI_tax_id") != "9606":
                    continue
                yield self._normalize_row(row)
