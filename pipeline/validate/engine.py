import json
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable
from typing import Any, Iterator

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from linkml.validator.report import Severity

from pipeline.ingest.schema import load_merged_schema
from pipeline.progress import iter_indexed_jsonl


@dataclass
class ValidationSummary:
    input_record_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ValidationOutcome:
    line_number: int
    record: dict[str, Any]
    accepted: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationResult:
    summary: ValidationSummary
    outcomes: list[ValidationOutcome] = field(default_factory=list)


def iter_staged_records(path: Path) -> Iterator[dict]:
    with path.open('r') as f:
        for line_number, line in enumerate(f):
            yield line_number, json.loads(line)

def load_validation_schema(schema_path: Path) -> dict:
    """Load source schema YAML for LinkML validation (imports merged)."""
    return load_merged_schema(schema_path)


def validate_records(
    records_path: Path,
    schema_path: Path,
    target_class: str,
    target_class_for_record: Callable[[dict], str] | None = None,
    ):
    outcomes = []
    summary = ValidationSummary()
    validator = Validator(
        load_validation_schema(schema_path),
        validation_plugins=[JsonschemaValidationPlugin(closed=True)],
    )
    resolve_target_class = target_class_for_record or (lambda _: target_class)

    for line_number, record in iter_indexed_jsonl(
        records_path,
        desc=f"validate {records_path.parent.name}",
        loads=json.loads,
    ):
        summary.input_record_count += 1
        record_target_class = resolve_target_class(record)

        report = validator.validate(record, target_class=record_target_class)
        errors = [
            r
            for r in report.results
            if r.severity in (Severity.ERROR, Severity.FATAL)
        ]

        if errors:
            summary.rejected_count += 1
            for error in errors:
                key = error.type
                summary.error_counts[key] = summary.error_counts.get(key, 0) + 1
            outcomes.append(ValidationOutcome(
                line_number=line_number,
                record=record,
                accepted=False,
                errors=[e.model_dump() for e in errors],
            ))
        else:
            summary.accepted_count += 1
            outcomes.append(ValidationOutcome(
                line_number=line_number,
                record=record,
                accepted=True,
                errors=[],
            ))

    return ValidationResult(
        summary=summary, 
        outcomes=outcomes
    )
