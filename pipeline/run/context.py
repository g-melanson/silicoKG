"""Pipeline run context loaded from a YAML instance."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceSpec:
    """One publisher source to include in a pipeline run."""

    source: str  # e.g. "ncbi"
    source_name: str  # e.g. "ncbi-gene-info"


@dataclass(frozen=True)
class PipelineRunContext:
    """User-defined context for a multi-stage pipeline run.

    Built from a YAML instance. Stage CLIs remain independent; this context
    only supplies the arguments those stages would otherwise take from argv.
    """

    sources: tuple[SourceSpec, ...]
    stages: tuple[str, ...] = ("ingest",)
    run_id: str | None = None
    snapshot_raw: bool = False
    verbose: bool = False
    progress: bool = True
    # Per-stage extras for later customization (target_class, etc.).
    stage_args: dict[str, dict] = field(default_factory=dict)
