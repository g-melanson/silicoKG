from __future__ import annotations
from pathlib import Path

from pipeline.validate.engine import validate_records

from tests.conftest import _write_jsonl
from tests.validate.conftest import GENE_INFO_SCHEMA
from tests.builders.staging import (
    build_staging_set,
    build_mutated_property_record,
    build_misnamed_property_record,
    build_missing_property_record,
)

def test_validate_summary_output(tmp_path: Path):
    test_records = build_staging_set()
    records_path = _write_jsonl(tmp_path, test_records)
    result = validate_records(
        records_path=records_path,
        schema_path=GENE_INFO_SCHEMA,
        target_class="NCBIGeneInfoRow",
    )
    summary = result.summary
    outcomes = result.outcomes
    assert summary.input_record_count == len(test_records)
    assert summary.accepted_count == sum(1 for outcome in outcomes if outcome.accepted)
    assert summary.rejected_count == sum(1 for outcome in outcomes if not outcome.accepted)


def test_misnamed_property_record_rejected(tmp_path: Path):
    test_records = build_misnamed_property_record()
    records_path = _write_jsonl(tmp_path, test_records)
    result = validate_records(
        records_path=records_path,
        schema_path=GENE_INFO_SCHEMA,
        target_class="NCBIGeneInfoRow",
    )
    assert "jsonschema validation" in result.summary.error_counts


def test_mutated_property_record_rejected(tmp_path: Path):
    test_records = build_mutated_property_record()
    records_path = _write_jsonl(tmp_path, test_records)
    result = validate_records(
        records_path=records_path,
        schema_path=GENE_INFO_SCHEMA,
        target_class="NCBIGeneInfoRow",
    )
    assert result.summary.rejected_count == 1
    assert "jsonschema validation" in result.summary.error_counts

def test_missing_property_record_accepted(tmp_path: Path):
    test_records = build_missing_property_record()
    records_path = _write_jsonl(tmp_path, test_records)
    result = validate_records(
        records_path=records_path,
        schema_path=GENE_INFO_SCHEMA,
        target_class="NCBIGeneInfoRow",
    )
    assert result.summary.accepted_count == 1
