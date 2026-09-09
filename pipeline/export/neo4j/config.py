"""Declarative Neo4j export configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.config import parse_str_set
from pipeline.export.neo4j.label_map import (
    DEFAULT_LABEL_MAP_PATH,
    SoLabelMap,
    load_label_map,
)
from pipeline.paths import REPO_ROOT

ARRAY_DELIMITER = "\x1f"
DBXREF_STUB_LABEL = "DbXref"


@dataclass(frozen=True)
class Neo4jExportConfig:
    """Rules applied when projecting gold tier to Neo4j CSV."""

    exclude_edge_types: frozenset[str] = frozenset()
    stub_nodes: bool = True
    stub_labels: frozenset[str] = frozenset({DBXREF_STUB_LABEL})
    exclude_node_properties: frozenset[str] = frozenset()
    label_map_path: Path = DEFAULT_LABEL_MAP_PATH
    label_map: SoLabelMap | None = field(default=None, compare=False)

    def resolved_label_map(self) -> SoLabelMap:
        if self.label_map is not None:
            return self.label_map
        return load_label_map(self.label_map_path)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> Neo4jExportConfig:
        if not raw:
            return cls()

        exclude_edge_types = parse_str_set(
            raw.get("exclude_edge_types"),
            field="export_neo4j.exclude_edge_types",
        )
        exclude_node_properties = parse_str_set(
            raw.get("exclude_node_properties"),
            field="export_neo4j.exclude_node_properties",
        )
        stub_labels = parse_str_set(
            raw.get("stub_labels"),
            field="export_neo4j.stub_labels",
        )
        if stub_labels is None:
            stub_labels = frozenset({DBXREF_STUB_LABEL})

        stub_nodes = raw.get("stub_nodes", True)
        if not isinstance(stub_nodes, bool):
            raise ValueError("export_neo4j.stub_nodes must be a boolean")

        label_map_raw = raw.get("label_map")
        if label_map_raw is None:
            label_map_path = DEFAULT_LABEL_MAP_PATH
        elif isinstance(label_map_raw, (str, Path)):
            label_map_path = Path(label_map_raw)
            if not label_map_path.is_absolute():
                label_map_path = REPO_ROOT / label_map_path
        else:
            raise ValueError("export_neo4j.label_map must be a path string")

        return cls(
            exclude_edge_types=exclude_edge_types or frozenset(),
            stub_nodes=stub_nodes,
            stub_labels=stub_labels,
            exclude_node_properties=exclude_node_properties or frozenset(),
            label_map_path=label_map_path,
        )

    @classmethod
    def resolve(
        cls,
        export_raw: dict[str, Any] | None,
        *,
        publish_raw: dict[str, Any] | None = None,
        gold_manifest_path: Path | None = None,
    ) -> Neo4jExportConfig:
        """Build export config, inheriting edge excludes from publish or gold manifest."""
        merged = dict(export_raw or {})
        if not merged.get("exclude_edge_types"):
            publish_excludes = (publish_raw or {}).get("exclude_edge_types")
            if publish_excludes:
                merged["exclude_edge_types"] = publish_excludes
            elif gold_manifest_path and gold_manifest_path.is_file():
                manifest = json.loads(gold_manifest_path.read_text(encoding="utf-8"))
                projection = manifest.get("projection", {})
                gold_excludes = projection.get("exclude_edge_types")
                if gold_excludes:
                    merged["exclude_edge_types"] = gold_excludes
        return cls.from_mapping(merged or None)
