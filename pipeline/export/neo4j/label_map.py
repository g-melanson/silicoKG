"""SO slot → Neo4j additional-label mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipeline.paths import REPO_ROOT

DEFAULT_LABEL_MAP_PATH = REPO_ROOT / "schemas/ontology/so-label-map.yaml"


class SoLabelMapError(ValueError):
    """Raised when so-label-map.yaml is missing or malformed."""


@dataclass(frozen=True)
class SoLabelMap:
    version: int
    # slot → {curie → additional Neo4j label}
    additional_labels: dict[str, dict[str, str]]

    def resolve_additional_labels(self, node: dict[str, Any]) -> tuple[str, ...]:
        labels: list[str] = []
        seen: set[str] = set()
        for slot, curie_map in self.additional_labels.items():
            values = node.get(slot)
            if values is None:
                continue
            items = values if isinstance(values, list) else [values]
            for item in items:
                label = curie_map.get(str(item))
                if label and label not in seen:
                    seen.add(label)
                    labels.append(label)
        return tuple(sorted(labels))


def load_label_map(path: Path | None = None) -> SoLabelMap:
    map_path = path or DEFAULT_LABEL_MAP_PATH
    if not map_path.is_absolute():
        map_path = REPO_ROOT / map_path
    if not map_path.is_file():
        raise SoLabelMapError(f"label map not found: {map_path}")

    with map_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise SoLabelMapError(f"label map root must be a mapping: {map_path}")

    try:
        version = int(data["version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SoLabelMapError("label map missing required field: version") from exc

    raw_labels = data.get("additional_labels") or {}
    if not isinstance(raw_labels, dict):
        raise SoLabelMapError("label map additional_labels must be a mapping")

    additional_labels: dict[str, dict[str, str]] = {}
    for slot, curie_map in raw_labels.items():
        if not isinstance(curie_map, dict):
            raise SoLabelMapError(
                f"label map additional_labels[{slot}] must be a mapping"
            )
        additional_labels[str(slot)] = {
            str(curie): str(label) for curie, label in curie_map.items()
        }

    return SoLabelMap(version=version, additional_labels=additional_labels)
