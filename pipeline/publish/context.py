from dataclasses import dataclass, field
from pathlib import Path

from pipeline.paths import DEFAULT_PATHS, REPO_ROOT, UniversePaths
from pipeline.publish.projection import DEFAULT_STRIP_SLOTS


@dataclass
class PublishContext:
    run_id: str
    merged_run_id: str | None = None
    schema_path: Path = field(
        default_factory=lambda: REPO_ROOT / "schemas/domain/gene-or-gene-product.yaml"
    )
    strip_slots: frozenset[str] = DEFAULT_STRIP_SLOTS
    paths: UniversePaths = DEFAULT_PATHS

    @property
    def effective_merged_run_id(self) -> str:
        return self.merged_run_id or self.run_id
