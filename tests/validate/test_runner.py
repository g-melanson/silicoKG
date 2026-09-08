import json
from pathlib import Path
from tests.validate.conftest import run_validate, RUN_ID, STAGING_RUN_ID, SOURCE, SOURCE_NAME, TARGET_CLASS
from tests.builders.staging import (
    build_staging_set,
    build_valid_staging_records,
    build_misnamed_property_record,
)

def test_validation_runner_writes_to_bronze(tmp_path: Path):
    paths = run_validate(
        tmp_path, 
        build_valid_staging_records()
    )

    bronze_rec = paths.bronze_records(source=SOURCE_NAME, run_id=RUN_ID)
    quarantine_rec = paths.bronze_quarantine(source=SOURCE_NAME, run_id=RUN_ID)

    assert bronze_rec.stat().st_size > 0
    assert quarantine_rec.stat().st_size == 0


def test_validation_runner_writes_to_quarantine(tmp_path: Path):
    paths = run_validate(
        tmp_path, 
        build_misnamed_property_record()
    )

    bronze_rec = paths.bronze_records(source=SOURCE_NAME, run_id=RUN_ID)
    quarantine_rec = paths.bronze_quarantine(source=SOURCE_NAME, run_id=RUN_ID)

    assert bronze_rec.stat().st_size == 0
    assert quarantine_rec.stat().st_size > 0

def test_validation_manifest_writes_to_bronze(tmp_path: Path):
    paths = run_validate(
        tmp_path, 
        build_valid_staging_records()
    )

    manifest_path = paths.bronze_manifest(source=SOURCE_NAME, run_id=RUN_ID)
    manifest = json.loads(manifest_path.read_text())

    assert manifest_path.exists() and manifest_path.stat().st_size > 0
    assert manifest["source_name"] == SOURCE_NAME
    assert manifest["run_id"] == RUN_ID
    assert manifest["target_class"] == TARGET_CLASS
    assert manifest["staging_run_id"] == STAGING_RUN_ID


def test_validation_runs_mixed_batch(tmp_path: Path):
    paths = run_validate(
        tmp_path, 
        build_staging_set()
    )

    manifest_path = paths.bronze_manifest(source=SOURCE_NAME, run_id=RUN_ID)
    manifest = json.loads(manifest_path.read_text())

    assert manifest["drift"]["input_record_count"] == 6
    assert manifest["drift"]["accepted_count"] == 4
    assert manifest["drift"]["rejected_count"] == 2


def test_validation_reads_staging_run_id_writes_run_id(tmp_path: Path):
    paths = run_validate(
        tmp_path, 
        build_valid_staging_records()
    )

    bronze_rec = paths.bronze_records(source=SOURCE_NAME, run_id=RUN_ID)
    bronze_manifest = paths.bronze_manifest(source=SOURCE_NAME, run_id=RUN_ID)

    assert bronze_rec.stat().st_size > 0
    assert bronze_manifest.exists()

    manifest = json.loads(bronze_manifest.read_text())
    assert manifest["run_id"] == RUN_ID
    assert manifest["staging_run_id"] == STAGING_RUN_ID

    # Nothing bronze-like under the staging run
    staging_bronze = paths.bronze_run_dir(source=SOURCE_NAME, run_id=STAGING_RUN_ID)
    assert not staging_bronze.exists()
