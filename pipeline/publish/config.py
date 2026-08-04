"""Declarative publish (gold projection) configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.config import parse_str_set
from pipeline.publish.projection import DEFAULT_STRIP_SLOTS


@dataclass(frozen=True)
class PublishConfig:
    """Rules applied when projecting merged tier to gold."""

    strip_slots: frozenset[str] = DEFAULT_STRIP_SLOTS
    exclude_edge_types: frozenset[str] = frozenset()

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> PublishConfig:
        if not raw:
            return cls()

        extra_strip_slots = parse_str_set(
            raw.get("strip_slots"),
            field="publish.strip_slots",
        )
        exclude_edge_types = parse_str_set(
            raw.get("exclude_edge_types"),
            field="publish.exclude_edge_types",
        )

        strip_slots = DEFAULT_STRIP_SLOTS
        if extra_strip_slots:
            strip_slots = strip_slots | extra_strip_slots

        return cls(
            strip_slots=strip_slots,
            exclude_edge_types=exclude_edge_types or frozenset(),
        )
