from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pipeline.ingest.context import IngestContext
from sources.base import BaseAdapter
from sources.corum.corum_human_complexes.parse import iter_corum_rows, load_complexes
from sources.registry import register

_ROW_KIND_TO_CLASS = {
    "complex": "CorumComplexRow",
    "subunit": "CorumSubunitRow",
    "function": "CorumFunctionRow",
    "fcg": "CorumFcgRow",
}


@register
class CorumHumanComplexesAdapter(BaseAdapter):
    source = "corum-human-complexes"
    target_class = "CorumComplexRow"
    schema_path = Path(__file__).with_name("corum-human-complexes.schema.yaml")
    ingest_required_fields = ()

    def target_class_for_record(self, record: dict) -> str:
        return _ROW_KIND_TO_CLASS[record["row_kind"]]

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        yield from iter_corum_rows(load_complexes(path))
