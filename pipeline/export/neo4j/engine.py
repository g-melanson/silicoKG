"""Neo4j bulk-import CSV generation from gold tier."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from pipeline.export.neo4j.config import Neo4jExportConfig
from pipeline.export.neo4j.label_map import SoLabelMap
from pipeline.publish.projection import omit_keys
from pipeline.progress import iter_indexed_jsonl

RESERVED_NODE_KEYS = frozenset({"id", "@type"})
RESERVED_EDGE_KEYS = frozenset({"id", "@type", "subject", "predicate", "object"})
ARRAY_PROPERTY_KEYS = frozenset(
    {
        "synonyms",
        "dbxrefs",
        "same_as",
        "so_types",
        "so_qualities",
        "class_labels",
        "pubmed_id",
    }
)
ARRAY_DELIMITER = ";"


@dataclass(frozen=True)
class NodeTypeExport:
    label: str
    path: Path
    count: int
    property_keys: tuple[str, ...]


@dataclass
class Neo4jExportSummary:
    node_count: int = 0
    dbxref_node_count: int = 0
    relationship_count: int = 0
    skipped_edge_count: int = 0
    node_types: list[NodeTypeExport] = field(default_factory=list)
    relationship_property_keys: list[str] = field(default_factory=list)

    @property
    def node_files(self) -> dict[str, Path]:
        return {entry.label: entry.path for entry in self.node_types}

    @property
    def node_property_keys_by_label(self) -> dict[str, list[str]]:
        return {entry.label: list(entry.property_keys) for entry in self.node_types}


def _iter_jsonl(path: Path, *, desc: str) -> Iterator[dict[str, Any]]:
    for _line_number, record in iter_indexed_jsonl(path, desc=desc, loads=json.loads):
        yield record


def _relationship_type(predicate: str) -> str:
    if ":" in predicate:
        return predicate.rsplit(":", 1)[-1]
    return predicate


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ARRAY_DELIMITER.join(str(item) for item in value)
    return str(value)


def _collect_node_ids(nodes_path: Path) -> set[str]:
    return {
        node["id"]
        for node in _iter_jsonl(nodes_path, desc="export node ids")
    }


def _should_export_edge(edge: dict[str, Any], config: Neo4jExportConfig) -> bool:
    edge_type = edge.get("@type")
    if edge_type in config.exclude_edge_types:
        return False
    return True


def _collect_external_endpoints(
    edges_path: Path,
    node_ids: set[str],
    config: Neo4jExportConfig,
) -> set[str]:
    if not config.stub_nodes:
        return set()

    external: set[str] = set()
    for edge in _iter_jsonl(edges_path, desc="scan edge endpoints"):
        if not _should_export_edge(edge, config):
            continue
        for endpoint in (edge.get("subject"), edge.get("object")):
            if endpoint and endpoint not in node_ids:
                external.add(endpoint)
    return external


def resolve_additional_labels(node: dict[str, Any], label_map: SoLabelMap) -> tuple[str, ...]:
    return label_map.resolve_additional_labels(node)


def node_export_label(base_type: str, additional: tuple[str, ...]) -> str:
    if not additional:
        return base_type
    return ":".join((base_type, *additional))


def node_csv_filename(base_type: str, additional: tuple[str, ...]) -> str:
    if not additional:
        return f"{base_type}.csv"
    return f"{base_type}__{'__'.join(additional)}.csv"


def _group_nodes_by_type(nodes_path: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in _iter_jsonl(nodes_path, desc="export nodes"):
        grouped[node["@type"]].append(node)
    return grouped


def _partition_nodes_by_labels(
    nodes: list[dict[str, Any]],
    label_map: SoLabelMap,
) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    partitions: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        partitions[resolve_additional_labels(node, label_map)].append(node)
    return partitions


def _property_keys_for_nodes(
    nodes: list[dict[str, Any]],
    config: Neo4jExportConfig,
) -> list[str]:
    keys: set[str] = set()
    for node in nodes:
        keys.update(omit_keys(node, RESERVED_NODE_KEYS | config.exclude_node_properties))
    return sorted(keys)


def _relationship_property_keys(edges_path: Path, config: Neo4jExportConfig) -> list[str]:
    keys: set[str] = set()
    for edge in _iter_jsonl(edges_path, desc="scan edge properties"):
        if not _should_export_edge(edge, config):
            continue
        keys.update(key for key in edge if key not in RESERVED_EDGE_KEYS)
    return sorted(keys)


def _node_header(property_keys: list[str]) -> list[str]:
    # Labels come from --nodes=Label1:Label2=file.csv, not the ID header.
    # neo4j-admin treats nodeId:ID:Label as types (ID, Label) and fails.
    header = ["nodeId:ID"]
    for key in property_keys:
        suffix = ":string[]" if key in ARRAY_PROPERTY_KEYS else ":string"
        header.append(f"{key}{suffix}")
    return header


def _relationship_header(property_keys: list[str]) -> list[str]:
    header = [":START_ID", ":END_ID", ":TYPE"]
    header.extend(f"{key}:string" for key in property_keys)
    return header


def _node_row(
    node_id: str,
    properties: dict[str, Any],
    property_keys: list[str],
) -> list[str]:
    row = [node_id]
    for key in property_keys:
        row.append(_format_cell(properties.get(key)))
    return row


def _node_properties(node: dict[str, Any], config: Neo4jExportConfig) -> dict[str, Any]:
    return omit_keys(
        node,
        RESERVED_NODE_KEYS | config.exclude_node_properties,
    )


def _write_node_type_csv(
    *,
    label: str,
    nodes: list[dict[str, Any]],
    output_path: Path,
    config: Neo4jExportConfig,
    property_keys: list[str] | None = None,
) -> NodeTypeExport:
    keys = property_keys or _property_keys_for_nodes(nodes, config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as node_file:
        writer = csv.writer(node_file)
        writer.writerow(_node_header(keys))
        for node in nodes:
            writer.writerow(
                _node_row(
                    node["id"],
                    _node_properties(node, config),
                    keys,
                )
            )
    return NodeTypeExport(
        label=label,
        path=output_path,
        count=len(nodes),
        property_keys=tuple(keys),
    )


def export_neo4j_csv(
    nodes_path: Path,
    edges_path: Path,
    *,
    nodes_csv_dir: Path,
    relationships_csv_path: Path,
    config: Neo4jExportConfig | None = None,
) -> Neo4jExportSummary:
    config = config or Neo4jExportConfig()
    label_map = config.resolved_label_map()
    node_ids = _collect_node_ids(nodes_path)
    external_ids = sorted(_collect_external_endpoints(edges_path, node_ids, config))
    relationship_property_keys = _relationship_property_keys(edges_path, config)

    node_types: list[NodeTypeExport] = []
    node_count = 0
    for base_label, nodes in sorted(_group_nodes_by_type(nodes_path).items()):
        partitions = _partition_nodes_by_labels(nodes, label_map)
        for additional, partition_nodes in sorted(partitions.items()):
            export_label = node_export_label(base_label, additional)
            filename = node_csv_filename(base_label, additional)
            export = _write_node_type_csv(
                label=export_label,
                nodes=partition_nodes,
                output_path=nodes_csv_dir / filename,
                config=config,
            )
            node_types.append(export)
            node_count += export.count

    if external_ids:
        stub_label = next(iter(config.stub_labels))
        stub_nodes = [{"id": curie, "curie": curie} for curie in external_ids]
        export = _write_node_type_csv(
            label=stub_label,
            nodes=stub_nodes,
            output_path=nodes_csv_dir / f"{stub_label}.csv",
            config=config,
            property_keys=["curie"],
        )
        node_types.append(export)
        node_count += export.count

    relationship_count = 0
    skipped_edge_count = 0
    known_endpoints = (node_ids | set(external_ids)) if config.stub_nodes else node_ids
    relationships_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with relationships_csv_path.open("w", encoding="utf-8", newline="") as rel_file:
        writer = csv.writer(rel_file)
        writer.writerow(_relationship_header(relationship_property_keys))
        for edge in _iter_jsonl(edges_path, desc="export relationships"):
            if not _should_export_edge(edge, config):
                skipped_edge_count += 1
                continue

            subject = edge.get("subject")
            object_id = edge.get("object")
            if subject not in known_endpoints or object_id not in known_endpoints:
                skipped_edge_count += 1
                continue

            properties = {
                key: value
                for key, value in edge.items()
                if key not in RESERVED_EDGE_KEYS
            }
            row = [
                subject,
                object_id,
                _relationship_type(edge.get("predicate", "")),
            ]
            row.extend(_format_cell(properties.get(key)) for key in relationship_property_keys)
            writer.writerow(row)
            relationship_count += 1

    return Neo4jExportSummary(
        node_count=node_count,
        dbxref_node_count=len(external_ids),
        relationship_count=relationship_count,
        skipped_edge_count=skipped_edge_count,
        node_types=node_types,
        relationship_property_keys=relationship_property_keys,
    )
