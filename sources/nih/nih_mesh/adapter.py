from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sources.base import BaseAdapter
from sources.nih.nih_mesh.parse import (
    iter_descriptor_records,
    load_allowlist,
    matches_allowlist,
    tree_hierarchy_edges,
)
from sources.registry import register


@register
class NIHMeshAdapter(BaseAdapter):
    source = "nih-mesh"
    target_class = "NIHMeshDescriptorRow"
    schema_path = Path(__file__).with_name("nih-mesh.schema.yaml")
    ingest_required_fields = ()

    def target_class_for_record(self, record: dict) -> str:
        if record.get("row_kind") == "edge":
            return "NIHMeshEdgeRow"
        return "NIHMeshDescriptorRow"

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        allowlist = load_allowlist()
        descriptors: dict[str, dict] = {}
        tree_to_ui: dict[str, str] = {}

        for record in iter_descriptor_records(path):
            if not matches_allowlist(record["tree_numbers"], allowlist):
                continue
            descriptors[record["descriptor_ui"]] = record
            for tree_number in record["tree_numbers"]:
                tree_to_ui[tree_number] = record["descriptor_ui"]

        for record in descriptors.values():
            yield {
                "row_kind": "descriptor",
                "descriptor_ui": record["descriptor_ui"],
                "label": record["label"],
                "tree_numbers": record["tree_numbers"],
                "scope_note": record.get("scope_note"),
                "synonyms": record.get("synonyms") or [],
            }

        for record in descriptors.values():
            for tree_number in record["tree_numbers"]:
                yield from tree_hierarchy_edges(tree_number, tree_to_ui, descriptors)
