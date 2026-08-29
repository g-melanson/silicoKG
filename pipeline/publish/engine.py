"""Stream merged nodes/edges and publish to gold tier."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from linkml.validator.report import Severity
from linkml_runtime.utils.schemaview import SchemaView

from pipeline.io.jsonl import loads_line
from pipeline.publish.projection import (
    DEFAULT_STRIP_SLOTS,
    project_record,
    validation_payload,
)
from pipeline.progress import iter_indexed_jsonl


@dataclass
class PublishOutcome:
    line_number: int
    kind: str
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
    yield from iter_indexed_jsonl(path, desc=desc, loads=loads_line)


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


def _record_errors(summary: PublishSummary, errors: list[dict[str, Any]]) -> None:
    for error in errors:
        key = error.get("type", "unknown")
        summary.error_counts[key] = summary.error_counts.get(key, 0) + 1


def publish_gold_record(
    record: dict[str, Any],
    *,
    line_number: int,
    kind: str,
    validator: Validator,
    strip_slots: frozenset[str],
) -> PublishOutcome:
    projected = project_record(record, strip_slots=strip_slots)
    errors = _validate_record(validator, projected)
    return PublishOutcome(
        line_number=line_number,
        kind=kind,
        record=projected,
        accepted=not errors,
        errors=errors,
    )


def publish_merged_paths(
    nodes_path: Path,
    edges_path: Path,
    *,
    schema_path: Path,
    strip_slots: frozenset[str] = DEFAULT_STRIP_SLOTS,
    exclude_edge_types: frozenset[str] = frozenset(),
) -> Iterator[PublishOutcome | PublishSummary]:
    validator = _load_validator(schema_path)
    summary = PublishSummary()

    for line_number, record in _iter_jsonl(nodes_path, desc="publish nodes"):
        summary.input_node_count += 1
        outcome = publish_gold_record(
            record,
            line_number=line_number,
            kind="node",
            validator=validator,
            strip_slots=strip_slots,
        )
        if outcome.accepted:
            summary.node_count += 1
        else:
            summary.quarantine_node_count += 1
            _record_errors(summary, outcome.errors)
        yield outcome

    for line_number, record in _iter_jsonl(edges_path, desc="publish edges"):
        summary.input_edge_count += 1
        outcome = publish_gold_record(
            record,
            line_number=line_number,
            kind="edge",
            validator=validator,
            strip_slots=strip_slots,
        )
        if not outcome.accepted:
            summary.quarantine_edge_count += 1
            _record_errors(summary, outcome.errors)
            yield outcome
            continue
        if outcome.record.get("@type") not in exclude_edge_types:
            summary.edge_count += 1
        yield outcome

    yield summary
