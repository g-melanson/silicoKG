from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.paths import DEFAULT_PATHS, REPO_ROOT, UniversePaths


@dataclass(frozen=True)
class IngestContext:
    run_id: str
    source: str  # e.g. "ncbi"
    source_name: str  # e.g. "ncbi-gene-info"
    paths: UniversePaths = DEFAULT_PATHS

    @property
    def input_dir(self) -> Path:
        return REPO_ROOT / "data" / self.source / self.source_name

    def input_path(self, file_name: str) -> Path:
        return self.input_dir / file_name
