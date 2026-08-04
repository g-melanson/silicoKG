from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from sources.base import TsvSchemaAdapter
from sources.registry import register

@register
class TFLinkInteractionsAdapter(TsvSchemaAdapter):
    sep: str = "\t"
    source = "tflink-tf-interactions"
    ingest_required_fields = ("tf_id", "target_id")
    target_class = "TFLinkInteractionRow"
    schema_path = Path(__file__).with_name("tflink-tf-interactions.schema.yaml")
    url = "https://cdn.netbiol.org/tflink/download_files/TFLink_Homo_sapiens_interactions_All_simpleFormat_v1.0.tsv.gz"

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        with open(path, 'r') as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                yield self._normalize_row(row)