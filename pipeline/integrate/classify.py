"""Classify silver fragments as nodes or edges."""

from __future__ import annotations

from pipeline.identity.constants import EDGE_CLASS_TO_PREDICATE, EDGE_CLASSES


def is_edge_class(class_name: str, obj: dict | None = None) -> bool:
    """Return True for LinkML reified edge classes (subject/object triples)."""
    if class_name in EDGE_CLASSES:
        return True
    if obj is not None:
        return bool(obj.get("subject") and obj.get("object"))
    return False


def validate_edge_object(obj: dict) -> list[str]:
    errors: list[str] = []
    if not obj.get("subject"):
        errors.append("edge missing subject")
    if not obj.get("object"):
        errors.append("edge missing object")
    predicate = obj.get("predicate") or EDGE_CLASS_TO_PREDICATE.get(obj.get("@type"))
    if not predicate:
        errors.append("edge missing predicate")
    return errors


def validate_envelope(fragment: dict) -> list[str]:
    errors: list[str] = []
    for key in ("class", "object", "source"):
        if key not in fragment:
            errors.append(f"missing envelope key: {key}")
    obj = fragment.get("object", {})
    if not obj.get("id"):
        errors.append("object.id is required")
    if not obj.get("@type"):
        errors.append("object.@type is required")
    source = fragment.get("source", {})
    if "source_name" not in source:
        errors.append("source.source_name is required")
    if "bronze_line" not in source:
        errors.append("source.bronze_line is required")
    return errors
