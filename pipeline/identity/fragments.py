"""Build silver fragment envelopes."""

from __future__ import annotations

from pipeline.identity.constants import EDGE_CLASS_TO_PREDICATE


def build_fragment_envelope(
    *,
    target_class: str,
    obj: dict,
    source_name: str,
    silver_run_id: str,
    bronze_line: int,
    bronze_record: dict,
) -> dict:
    source = {
        "source_name": source_name,
        "silver_run_id": silver_run_id,
        "bronze_line": bronze_line,
    }
    if bronze_record.get("gene_id") is not None:
        source["gene_id"] = str(bronze_record["gene_id"])
    if bronze_record.get("tax_id") is not None:
        source["tax_id"] = str(bronze_record["tax_id"])

    return {
        "class": target_class,
        "object": obj,
        "source": source,
    }


def build_quarantine_line(
    *,
    bronze_line: int,
    target_class: str,
    bronze_record: dict,
    errors: list[str],
) -> dict:
    return {
        "bronze_line": bronze_line,
        "target_class": target_class,
        "bronze_record": bronze_record,
        "errors": errors,
    }


def ensure_edge_predicate(obj: dict) -> dict:
    """Attach predicate CURIE from edge class when absent."""
    edge_type = obj.get("@type")
    if edge_type in EDGE_CLASS_TO_PREDICATE and not obj.get("predicate"):
        obj = dict(obj)
        obj["predicate"] = EDGE_CLASS_TO_PREDICATE[edge_type]
    return obj
