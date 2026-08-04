from __future__ import annotations

import pandas as pd
from collections.abc import Iterator
from pathlib import Path

from sources.base import TsvSchemaAdapter
from sources.registry import register


def build_all_synonyms(row: dict) -> list[str]:
    """Merge synonym-like fields with order preserved and duplicates removed.

    Order: symbol (0–1), synonyms, symbol_from_nomenclature_authority (0–1),
    full_name_from_nomenclature_authority (0–1), other_designations.
    Empty / null inputs are skipped; result is ``[]`` when nothing remains.
    """
    parts: list[str] = []
    symbol = row.get("symbol")
    if symbol:
        parts.append(symbol)
    synonyms = row.get("synonyms") or []
    if isinstance(synonyms, list):
        parts.extend(synonyms)
    elif synonyms:
        parts.append(synonyms)
    symbol_auth = row.get("symbol_from_nomenclature_authority")
    if symbol_auth:
        parts.append(symbol_auth)
    full_name = row.get("full_name_from_nomenclature_authority")
    if full_name:
        parts.append(full_name)
    other = row.get("other_designations") or []
    if isinstance(other, list):
        parts.extend(other)
    elif other:
        parts.append(other)
    return list(dict.fromkeys(parts))


@register
class NCBIGeneInfoAdapter(TsvSchemaAdapter):
    source = "ncbi-gene-info"
    target_class = "NCBIGeneInfoRow"
    schema_path = Path(__file__).with_name("ncbi-gene-info.schema.yaml")
    url = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"

    def _normalize_row(self, raw_row: dict) -> dict:
        normalized = super()._normalize_row(raw_row)
        normalized["all_synonyms"] = build_all_synonyms(normalized)
        return normalized

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
