"""Project merged records to gold consumer shape."""

from __future__ import annotations

from typing import Any

DEFAULT_STRIP_SLOTS = frozenset({"sources", "alternates", "dbxrefs", "same_as"})
VALIDATION_EXCLUDE = DEFAULT_STRIP_SLOTS | frozenset({"@type", "predicate"})


def omit_keys(record: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    """Return a shallow copy of record without the given top-level keys."""
    return {key: value for key, value in record.items() if key not in keys}


def project_record(
    record: dict[str, Any],
    strip_slots: frozenset[str] = DEFAULT_STRIP_SLOTS,
) -> dict[str, Any]:
    """Return a gold record with internal merge metadata removed."""
    return omit_keys(record, strip_slots)


def validation_payload(
    record: dict[str, Any],
    exclude: frozenset[str] = VALIDATION_EXCLUDE,
) -> dict[str, Any]:
    """Return the subset of a record used for domain schema validation."""
    return omit_keys(record, exclude)
