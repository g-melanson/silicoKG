from __future__ import annotations

import csv
import pandas as pd
from collections.abc import Iterator
from pathlib import Path

from sources.base import TsvSchemaAdapter
from sources.registry import register

@register
class NCBIGeneSummaryAdapter(TsvSchemaAdapter):
    source = "ncbi-gene-summary"
    target_class = "NCBIGeneSummaryRow"
    schema_path = Path(__file__).with_name("ncbi-gene-summary.schema.yaml")
    url = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_summary.gz"

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        df = pd.read_csv(path, sep=self.sep, dtype=str, keep_default_na=False)
        df.columns = [c.lstrip(self.header_prefix) for c in df.columns]
        for _, row in df[df["tax_id"] == "9606"].iterrows():
            yield self._normalize_row(row.to_dict())