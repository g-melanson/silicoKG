from __future__ import annotations
import pandas as pd
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from pipeline.ingest.schema import (
    field_ranges,
    load_source_schema,
    multivalued_delimiters,
    publisher_field_map,
)

if TYPE_CHECKING:
    from pipeline.ingest.context import IngestContext

TYPE_CONVERTERS = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
}


class BaseAdapter(ABC):
    source: ClassVar[str]
    ingest_required_fields: ClassVar[tuple[str, ...]] = ("tax_id", "gene_id")

    @abstractmethod
    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        """Read a publisher raw file and yield normalized row dicts."""

class SchemaBackedAdapter(BaseAdapter):
    """Schema-driven row normalization; subclasses only implement parse()."""
    target_class: ClassVar[str]
    schema_path: ClassVar[Path]
    missing_values: ClassVar[frozenset[str]] = frozenset({"", "-"})
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "schema_path", None):
            schema = load_source_schema(cls.schema_path)
            cls.source_schema = schema
            cls.field_map = publisher_field_map(schema, target_class=cls.target_class)
            cls.data_types = field_ranges(schema, target_class=cls.target_class)
            cls.multivalued = multivalued_delimiters(schema, target_class=cls.target_class)

    def _normalize_row(self, raw_row: dict) -> dict:
        mapped = {
            self.field_map.get(key, key): value
            for key, value in raw_row.items()
            if key is not None
        }

        normalized: dict = {}
        for key, value in mapped.items():

            if key not in self.data_types:
                continue

            if value is None or value == "" or value in self.missing_values:
                normalized[key] = [] if key in self.multivalued else None
                continue

            if key in self.multivalued:
                delim = self.multivalued[key]
                parts = [p for p in value.split(delim)]
                converter = TYPE_CONVERTERS[self.data_types[key]]
                normalized[key] = [converter(p) for p in parts]

            else:
                converter = TYPE_CONVERTERS[self.data_types[key]]
                normalized[key] = converter(value)

        return normalized


class TsvSchemaAdapter(SchemaBackedAdapter):
    """Tab-separated publisher files (common NCBI pattern)."""
    sep: ClassVar[str] = "\t"
    header_prefix: ClassVar[str] = "#"
    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        df = pd.read_csv(path, sep=self.sep, dtype=str, keep_default_na=False)
        df.columns = [c.lstrip(self.header_prefix) for c in df.columns]
        for _, row in df.iterrows():
            yield self._normalize_row(row.to_dict())
