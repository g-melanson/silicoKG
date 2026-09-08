from pathlib import Path
from pipeline.paths import UniversePaths, REPO_ROOT
from pipeline.validate.runner import run

from tests.conftest import _write_jsonl

RUN_ID = "validate-y"
SOURCE = "ncbi"
SOURCE_NAME = "ncbi-gene-info"
STAGING_RUN_ID = "ingest-x"
TARGET_CLASS = "NCBIGeneInfoRow"
GENE_INFO_SCHEMA = REPO_ROOT / "sources/ncbi/ncbi_gene_info/ncbi-gene-info.schema.yaml"

def run_validate(
    tmp_path: Path,
    records: list[dict],
    staging_run_id: str = STAGING_RUN_ID,
    run_id: str = RUN_ID,
):
    paths = UniversePaths(root=tmp_path / "universe")

    staging_dir = paths.staging_run_dir(SOURCE_NAME, run_id=staging_run_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(staging_dir, records)

    run(
        source=SOURCE,
        source_name=SOURCE_NAME,
        target_class=TARGET_CLASS,
        staging_run_id=staging_run_id,
        run_id=run_id,
        paths=paths
    )

    return paths

