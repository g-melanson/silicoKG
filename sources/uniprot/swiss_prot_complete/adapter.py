from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pipeline.ingest.context import IngestContext
from sources.base import SchemaBackedAdapter
from sources.registry import register
from sources.uniprot.parse import iter_uniprot_entries


@register
class UniProtSwissProtCompleteAdapter(SchemaBackedAdapter):
    source = "swiss-prot-complete"
    target_class = "UniProtSwissProtRow"
    schema_path = Path(__file__).with_name("swiss-prot-complete.schema.yaml")
    ingest_required_fields = ("accession", "sequence", "tax_id")

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        for raw_row in iter_uniprot_entries(
            path,
            human_only=True,
            progress_desc=f"parse {self.source}",
        ):
            yield self._normalize_row(raw_row)
