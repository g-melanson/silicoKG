from __future__ import annotations

import yaml
from collections.abc import Iterator
from pathlib import Path

from sources.base import SchemaBackedAdapter
from sources.registry import register


@register
class UniProtGafAdapter(SchemaBackedAdapter):
    source = "uniprot-gaf"
    target_class = "UniProtGafRow"
    schema_path = Path(__file__).with_name("uniprot-gaf.schema.yaml")
    mapping_path = Path(__file__).with_name("uniprot-gaf.mapping.yaml")
    ingest_required_fields = ("db_object_id", "go_id", "relation")

    def _load_mapping(self) -> dict:
        with self.mapping_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _col(parts: list[str], index: int) -> str:
        if index >= len(parts):
            return ""
        return parts[index].strip()

    @staticmethod
    def _parse_taxon(raw: str) -> str:
        if raw.startswith("taxon:"):
            return raw.removeprefix("taxon:")
        return raw

    def _parse_qualifier(self, raw: str, *, negated_prefix: str) -> tuple[str, bool]:
        if raw.startswith(negated_prefix):
            return raw.removeprefix(negated_prefix), True
        return raw, False

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        mapping = self._load_mapping()
        columns = mapping["columns"]
        filter_tax = mapping.get("filter", {}).get("tax_id")
        negated_prefix = mapping.get("predicates", {}).get("negated_prefix", "NOT|")

        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip("\n")
                if not line or line.startswith("!"):
                    continue

                parts = line.split("\t")
                tax_id = self._parse_taxon(self._col(parts, columns["taxon"]))
                if filter_tax and tax_id != filter_tax:
                    continue

                relation, negated = self._parse_qualifier(
                    self._col(parts, columns["qualifier"]),
                    negated_prefix=negated_prefix,
                )
                if not relation or not self._col(parts, columns["go_id"]):
                    continue

                raw_row = {
                    "db": self._col(parts, columns["db"]),
                    "db_object_id": self._col(parts, columns["db_object_id"]),
                    "db_object_symbol": self._col(parts, columns["db_object_symbol"]),
                    "relation": relation,
                    "go_id": self._col(parts, columns["go_id"]),
                    "reference": self._col(parts, columns["reference"]),
                    "evidence_code": self._col(parts, columns["evidence_code"]),
                    "with_from": self._col(parts, columns["with_from"]),
                    "aspect": self._col(parts, columns["aspect"]),
                    "db_object_name": self._col(parts, columns["db_object_name"]),
                    "db_object_synonym": self._col(parts, columns["db_object_synonym"]),
                    "db_object_type": self._col(parts, columns["db_object_type"]),
                    "tax_id": tax_id,
                    "annotation_date": self._col(parts, columns["annotation_date"]),
                    "assigned_by": self._col(parts, columns["assigned_by"]),
                    "annotation_extension": self._col(
                        parts, columns["annotation_extension"]
                    ),
                    "gene_product_form_id": self._col(
                        parts, columns["gene_product_form_id"]
                    ),
                }
                normalized = self._normalize_row(raw_row)
                normalized["negated"] = negated
                yield normalized
