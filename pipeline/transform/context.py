from dataclasses import dataclass

from pipeline.paths import UniversePaths, DEFAULT_PATHS


@dataclass
class TransformContext:
    run_id: str
    bronze_run_id: str
    source: str
    source_name: str
    paths: UniversePaths = DEFAULT_PATHS
    workers: int = 1
    limit: int | None = None
