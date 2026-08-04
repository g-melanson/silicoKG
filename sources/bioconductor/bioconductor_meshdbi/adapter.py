from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pipeline.ingest.context import IngestContext
from sources.base import SchemaBackedAdapter
from sources.bioconductor.bioconductor_meshdbi.parse import iter_gene_mesh_rows_for_ingest
from sources.registry import register


@register
class BioconductorMeshDBIAdapter(SchemaBackedAdapter):
    source = "bioconductor-meshdbi"
    target_class = "BioconductorMeshDBIRow"
    schema_path = Path(__file__).with_name("bioconductor-meshdbi.schema.yaml")
    ingest_required_fields = ("gene_id", "mesh_id")

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        if ctx is None:
            raise ValueError("bioconductor-meshdbi ingest requires IngestContext")
        for row in iter_gene_mesh_rows_for_ingest(path, ctx=ctx):
            yield self._normalize_row(row)
