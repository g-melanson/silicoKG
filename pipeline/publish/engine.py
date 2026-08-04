"""Stream merged nodes/edges and publish to gold tier."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from linkml.validator.report import Severity
from linkml_runtime.utils.schemaview import SchemaView

from pipeline.publish.projection import (
    DEFAULT_STRIP_SLOTS,
    project_record,
    validation_payload,
)
from pipeline.progress import iter_indexed_jsonl


@dataclass
class PublishOutcome:
    line_number: int
    record: dict[str, Any]
    accepted: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PublishSummary:
    input_node_count: int = 0
    input_edge_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    quarantine_node_count: int = 0
    quarantine_edge_count: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


def _iter_jsonl(path: Path, *, desc: str) -> Iterator[tuple[int, dict[str, Any]]]:
    import json

    yield from iter_indexed_jsonl(path, desc=desc, loads=json.loads)


def _load_validator(schema_path: Path) -> Validator:
    schema_view = SchemaView(str(schema_path))
    return Validator(
        schema_view.schema,
        validation_plugins=[JsonschemaValidationPlugin(closed=True)],
    )


def _validate_record(
    validator: Validator,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    target_class = record.get("@type")
    if not target_class:
        return [{"type": "missing_type", "message": "record missing @type"}]

    payload = validation_payload(record)
    report = validator.validate(payload, target_class=target_class)
    return [
        error.model_dump()
        for error in report.results
        if error.severity in (Severity.ERROR, Severity.FATAL)
    ]


def _publish_records(
    path: Path,
    validator: Validator,
    strip_slots: frozenset[str],
    *,
    desc: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, dict[str, int]]:
    accepted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    error_counts: dict[str, int] = {}

    for line_number, record in _iter_jsonl(path, desc=desc):
        projected = project_record(record, strip_slots=strip_slots)
        errors = _validate_record(validator, projected)
        if errors:
            for error in errors:
                key = error.get("type", "unknown")
                error_counts[key] = error_counts.get(key, 0) + 1
            quarantine.append(
                {
                    "line_number": line_number,
                    "record": projected,
                    "errors": errors,
                }
            )
        else:
            accepted.append(projected)

    return accepted, quarantine, len(accepted) + len(quarantine), error_counts


def _drop_edge_types(
    edges: list[dict[str, Any]],
    exclude_edge_types: frozenset[str],
) -> list[dict[str, Any]]:
    if not exclude_edge_types:
        return edges
    return [edge for edge in edges if edge.get("@type") not in exclude_edge_types]


def publish_merged_paths(
    nodes_path: Path,
    edges_path: Path,
    *,
    schema_path: Path,
    strip_slots: frozenset[str] = DEFAULT_STRIP_SLOTS,
    exclude_edge_types: frozenset[str] = frozenset(),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], PublishSummary]:
    validator = _load_validator(schema_path)

    nodes, quarantine_nodes, input_node_count, node_error_counts = _publish_records(
        nodes_path, validator, strip_slots, desc="publish nodes"
    )
    edges, quarantine_edges, input_edge_count, edge_error_counts = _publish_records(
        edges_path, validator, strip_slots, desc="publish edges"
    )
    edges = _drop_edge_types(edges, exclude_edge_types)

    error_counts = dict(node_error_counts)
    for key, count in edge_error_counts.items():
        error_counts[key] = error_counts.get(key, 0) + count

    summary = PublishSummary(
        input_node_count=input_node_count,
        input_edge_count=input_edge_count,
        node_count=len(nodes),
        edge_count=len(edges),
        quarantine_node_count=len(quarantine_nodes),
        quarantine_edge_count=len(quarantine_edges),
        error_counts=error_counts,
    )
    return nodes, edges, quarantine_nodes, quarantine_edges, summary
