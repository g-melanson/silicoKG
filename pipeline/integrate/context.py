from dataclasses import dataclass

from pipeline.paths import DEFAULT_PATHS, UniversePaths


@dataclass
class IntegrateContext:
    run_id: str
    source_names: tuple[str, ...]
    priorities_path: str | None = None
    paths: UniversePaths = DEFAULT_PATHS
