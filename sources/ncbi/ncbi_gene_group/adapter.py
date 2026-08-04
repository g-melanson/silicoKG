from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from sources.base import TsvSchemaAdapter
from sources.registry import register

# NCBI gene_group relationship → (edge class, predicate CURIE)
RELATIONSHIP_EDGE: dict[str, tuple[str, str]] = {
    "Related pseudogene": ("GeneHasPseudogene", "silkg:PSEUDOGENE"),
    "Readthrough parent": ("GeneHasReadthroughParent", "silkg:READTHROUGH_PARENT"),
    "Readthrough sibling": ("GeneHasReadthroughSibling", "silkg:READTHROUGH_SIBLING"),
    "Region parent": ("GeneHasRegionParent", "silkg:REGION_PARENT"),
}


@register
class NCBIGeneGroupAdapter(TsvSchemaAdapter):
    source = "ncbi-gene-group"
    target_class = "NCBIGeneGroupRow"
    schema_path = Path(__file__).with_name("ncbi-gene-group.schema.yaml")
    url = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_group.gz"

    def _normalize_row(self, raw_row: dict) -> dict:
        """Normalize publisher fields and derive edge URIs for transform.

        Object Gene URI uses ``tax_id`` (not ``other_tax_id``) to match the
        historical gene-group transform expressions.
        """
        normalized = super()._normalize_row(raw_row)
        tax_id = normalized.get("tax_id")
        gene_id = normalized.get("gene_id")
        other_gene_id = normalized.get("other_gene_id")
        relationship = normalized.get("relationship")

        normalized["subject_uri"] = (
            f"silkg:Gene:{tax_id}:{gene_id}" if tax_id and gene_id else None
        )
        normalized["object_uri"] = (
            f"silkg:Gene:{tax_id}:{other_gene_id}"
            if tax_id and other_gene_id
            else None
        )

        edge = RELATIONSHIP_EDGE.get(relationship) if relationship else None
        if edge and tax_id and gene_id and other_gene_id:
            edge_class, predicate = edge
            normalized["edge_class"] = edge_class
            normalized["edge_predicate"] = predicate
            normalized["edge_id"] = (
                f"silkg:{edge_class}:{tax_id}:{gene_id}:{other_gene_id}"
            )
        else:
            normalized["edge_class"] = None
            normalized["edge_predicate"] = None
            normalized["edge_id"] = None
        return normalized

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        with path.open(newline="", encoding="utf-8") as f:
            header_line = f.readline()
            fieldnames = [
                col.lstrip(self.header_prefix)
                for col in header_line.rstrip("\n").split(self.sep)
            ]
            reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=self.sep)
            for raw_row in reader:
                normalized = self._normalize_row(raw_row)
                if (
                    normalized.get("tax_id") != "9606"
                    and normalized.get("other_tax_id") != "9606"
                ):
                    continue
                yield normalized
