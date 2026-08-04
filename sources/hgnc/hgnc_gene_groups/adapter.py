from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pipeline.ingest.context import IngestContext
from sources.base import BaseAdapter
from sources.hgnc.hgnc_gene_groups.parse import iter_hgnc_gene_group_rows
from sources.registry import register


@register
class HGNCGeneGroupsAdapter(BaseAdapter):
    source = "hgnc-gene-groups"
    target_class = "HGNCGeneGroupRow"
    schema_path = Path(__file__).with_name("hgnc-gene-groups.schema.yaml")
    ingest_required_fields = ()

    def target_class_for_record(self, record: dict) -> str:
        row_kind = record.get("row_kind")
        if row_kind == "hierarchy_edge":
            return "HGNCGeneGroupHierarchyRow"
        if row_kind == "membership_edge":
            return "HGNCGeneGroupMembershipRow"
        return "HGNCGeneGroupRow"

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        cache_dir = ctx.paths.source_cache_dir(self.source) if ctx else None
        yield from iter_hgnc_gene_group_rows(path, cache_dir=cache_dir)
