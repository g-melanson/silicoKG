"""Fold bronze ontology rows into a compiled index document."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pipeline.ontology.adapters import OntologyEdgeRow, OntologyTermRow

_IS_A_PREDICATE = "rdfs:subClassOf"


@dataclass
class IndexStats:
    class_count: int = 0
    restriction_count: int = 0


@dataclass
class CompiledIndex:
    version: int
    source_name: str
    input_hash: str
    classes: dict[str, dict[str, Any]] = field(default_factory=dict)
    restrictions_index: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    stats: IndexStats = field(default_factory=IndexStats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_name": self.source_name,
            "input_hash": self.input_hash,
            "classes": self.classes,
            "restrictions_index": self.restrictions_index,
        }


def compile_index(
    rows: Iterable[OntologyTermRow | OntologyEdgeRow],
    *,
    source_name: str,
    input_hash: str,
) -> CompiledIndex:
    """Fold term and edge rows into the cached index shape."""
    index = CompiledIndex(
        version=1,
        source_name=source_name,
        input_hash=input_hash,
    )

    for row in rows:
        if isinstance(row, OntologyTermRow):
            index.classes[row.term_id] = {
                "label": row.label or "",
                "parents": [],
            }
            index.stats.class_count += 1
            continue

        if not isinstance(row, OntologyEdgeRow):
            continue

        if row.predicate_id == _IS_A_PREDICATE:
            entry = index.classes.setdefault(
                row.subject_id,
                {"label": "", "parents": []},
            )
            entry["parents"].append(row.object_id)
            continue

        index.restrictions_index.setdefault(row.subject_id, []).append(
            {
                "type": "some_values_from",
                "property": row.predicate_id,
                "filler": row.object_id,
            }
        )
        index.stats.restriction_count += 1

    return index


def write_index(index: CompiledIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            index.to_dict(),
            handle,
            sort_keys=False,
            allow_unicode=True,
        )


class OntologyIndexError(ValueError):
    """Raised when a compiled ontology index YAML is missing or malformed."""


def load_index(path: Path) -> CompiledIndex:
    """Load a compiled ontology index document written by ``write_index``."""
    if not path.is_file():
        raise OntologyIndexError(f"ontology index not found: {path}")

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise OntologyIndexError(f"ontology index root must be a mapping: {path}")

    try:
        version = int(data["version"])
        source_name = str(data["source_name"])
        input_hash = str(data["input_hash"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OntologyIndexError(
            f"ontology index missing required fields (version, source_name, input_hash): {path}"
        ) from exc

    classes = data.get("classes") or {}
    restrictions_index = data.get("restrictions_index") or {}
    if not isinstance(classes, dict):
        raise OntologyIndexError(f"ontology index classes must be a mapping: {path}")
    if not isinstance(restrictions_index, dict):
        raise OntologyIndexError(
            f"ontology index restrictions_index must be a mapping: {path}"
        )

    return CompiledIndex(
        version=version,
        source_name=source_name,
        input_hash=input_hash,
        classes=dict(classes),
        restrictions_index={
            str(class_id): list(restrictions or [])
            for class_id, restrictions in restrictions_index.items()
        },
        stats=IndexStats(
            class_count=len(classes),
            restriction_count=sum(len(v or []) for v in restrictions_index.values()),
        ),
    )
