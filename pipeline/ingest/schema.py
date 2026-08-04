from __future__ import annotations

import copy
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.utils.schemaview import SchemaView

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHER_HEADER_TAGS = ("silkg:publisher_header", "path:publisher_header")


def _resolve_schema_path(schema_path: str | Path) -> Path:
    path = Path(schema_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _has_attribute_delimiters(schema: dict[str, Any]) -> bool:
    for cls_def in (schema.get("classes") or {}).values():
        for slot_def in (cls_def.get("attributes") or {}).values():
            if isinstance(slot_def, dict) and "delimiter" in slot_def:
                return True
    return False


def _strip_attribute_delimiters(schema: dict[str, Any]) -> None:
    for cls_def in (schema.get("classes") or {}).values():
        for slot_def in (cls_def.get("attributes") or {}).values():
            if isinstance(slot_def, dict):
                slot_def.pop("delimiter", None)


def _load_schema_view(path: Path, raw: dict[str, Any]) -> SchemaView:
    """Load SchemaView from disk so relative imports resolve correctly."""
    if not _has_attribute_delimiters(raw):
        return SchemaView(str(path))

    cleaned = copy.deepcopy(raw)
    _strip_attribute_delimiters(cleaned)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
    ) as handle:
        yaml.dump(cleaned, handle, sort_keys=False)
        temp_path = handle.name
    try:
        return SchemaView(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def _schema_view_to_merged_dict(schema_view: SchemaView) -> dict[str, Any]:
    """Flatten imported modules into one dict safe for Validator/SchemaView(dict)."""
    data = yaml.safe_load(yaml_dumper.dumps(schema_view.schema))
    data["classes"] = {
        name: yaml.safe_load(yaml_dumper.dumps(cls))
        for name, cls in schema_view.all_classes(imports=True).items()
    }
    enums = schema_view.all_enums(imports=True)
    if enums:
        data["enums"] = {
            name: yaml.safe_load(yaml_dumper.dumps(enum))
            for name, enum in enums.items()
        }
    slots = schema_view.all_slots(imports=True)
    if slots:
        data["slots"] = {
            name: yaml.safe_load(yaml_dumper.dumps(slot))
            for name, slot in slots.items()
        }
    types = schema_view.all_types(imports=True)
    if types:
        data["types"] = {
            name: yaml.safe_load(yaml_dumper.dumps(typ))
            for name, typ in types.items()
        }
    for schema in schema_view.all_schema(imports=True):
        if schema.prefixes:
            data.setdefault("prefixes", {}).update(dict(schema.prefixes))
    data.pop("imports", None)
    _strip_attribute_delimiters(data)
    return data


@lru_cache
def load_source_schema(schema_path: str | Path) -> dict[str, Any]:
    """Load a source schema YAML from an absolute or repo-relative path."""
    path = _resolve_schema_path(schema_path)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def load_merged_schema(schema_path: str | Path) -> dict[str, Any]:
    """Load a schema and merge imported modules into one LinkML-valid dict."""
    path = _resolve_schema_path(schema_path)
    raw = load_source_schema(path)
    schema_view = _load_schema_view(path, raw)
    return _schema_view_to_merged_dict(schema_view)


def publisher_header_from_slot(slot_def: dict[str, Any]) -> str | None:
    annotations = slot_def.get("annotations") or {}
    for tag in PUBLISHER_HEADER_TAGS:
        if header := annotations.get(tag):
            return header
    return None


def publisher_field_map(
    schema: dict[str, Any],
    *,
    target_class: str,
) -> dict[str, str]:
    """publisher/xml/csv header -> normalized slot name."""
    attrs = schema["classes"][target_class]["attributes"]
    return {
        header: slot_name
        for slot_name, slot_def in attrs.items()
        if (header := publisher_header_from_slot(slot_def))
    }


def field_ranges(
    schema: dict[str, Any],
    *,
    target_class: str,
) -> dict[str, str]:
    """normalized slot name -> LinkML range (e.g. string, integer)."""
    attrs = schema["classes"][target_class]["attributes"]
    return {
        slot_name: (slot_def.get("range") or "string")
        for slot_name, slot_def in attrs.items()
    }


def multivalued_delimiters(
    schema: dict[str, Any],
    *,
    target_class: str,
) -> dict[str, str]:
    """normalized slot name -> delimiter for multivalued attributes."""
    attrs = schema["classes"][target_class]["attributes"]
    return {
        slot_name: slot_def["delimiter"]
        for slot_name, slot_def in attrs.items()
        if slot_def.get("multivalued") and slot_def.get("delimiter")
    }


def normalized_fields(
    schema: dict[str, Any],
    *,
    target_class: str,
) -> tuple[str, ...]:
    return tuple(schema["classes"][target_class]["attributes"].keys())


def source_field_map(rec: dict, row_class: str, FIELD_MAPS: dict) -> dict:
    """Rename publisher CSV columns to schema slots, keeping only known columns."""
    return {
        slot: rec.get(header)
        for header, slot in FIELD_MAPS[row_class].items()
        if header in rec
    }
