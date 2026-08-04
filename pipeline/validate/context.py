from pipeline.paths import UniversePaths, DEFAULT_PATHS
from dataclasses import dataclass

@dataclass
class ValidateContext:
    run_id: str
    staging_run_id: str
    source: str
    source_name: str
    target_class: str
    paths: UniversePaths = DEFAULT_PATHS
