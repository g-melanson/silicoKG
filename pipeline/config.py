"""Shared configuration parsing for pipeline stages."""

from __future__ import annotations

from typing import Any

def parse_str_set(value: Any, *, field: str) -> frozenset[str] | None:
    """Parse a YAML list of non-empty strings into a frozenset."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings")
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field}[{index}] must be a non-empty string")
        items.append(item.strip())
    return frozenset(items)
