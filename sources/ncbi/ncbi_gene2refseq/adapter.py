from __future__ import annotations

import csv
import pandas as pd
from collections.abc import Iterator
from pathlib import Path

from sources.base import TsvSchemaAdapter
from sources.registry import register

@register
class NCBIGene2RefSeqAdapter(TsvSchemaAdapter):
    source = "ncbi-gene2refseq"
    target_class = "NCBIGene2RefSeqRow"
    schema_path = Path(__file__).with_name("ncbi-gene2refseq.schema.yaml")
    url = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2refseq.gz"

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        with path.open(newline="", encoding="utf-8") as f:
            header_line = f.readline()
            fieldnames = [
                col.lstrip(self.header_prefix)
                for col in header_line.rstrip("\n").split(self.sep)
            ]
            reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=self.sep)
            for raw_row in reader:
                normalized = self._normalize_row(raw_row)
                if normalized.get("tax_id") != "9606":
                    continue
                yield normalized
