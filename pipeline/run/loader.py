"""Load and validate a pipeline run YAML instance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pipeline.run.context import PipelineRunContext, SourceSpec

KNOWN_STAGES = (
    "ingest",
    "validate",
    "transform",
    "integrate",
    "classify",
    "publish",
    "export_neo4j",
)


class PipelineRunConfigError(ValueError):
    """Raised when a run YAML is missing required fields or is malformed."""


def _require_non_empty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PipelineRunConfigError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_sources(raw: Any) -> tuple[SourceSpec, ...]:
    if not isinstance(raw, list) or not raw:
        raise PipelineRunConfigError(
            "sources must be a non-empty list (>= 1 source and >= 1 source_name)"
        )

    sources: list[SourceSpec] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PipelineRunConfigError(f"sources[{i}] must be a mapping")
        if "source" not in item:
            raise PipelineRunConfigError(f"sources[{i}] missing required field: source")
        if "source_name" not in item:
            raise PipelineRunConfigError(
                f"sources[{i}] missing required field: source_name"
            )
        sources.append(
            SourceSpec(
                source=_require_non_empty_str(item["source"], f"sources[{i}].source"),
                source_name=_require_non_empty_str(
                    item["source_name"], f"sources[{i}].source_name"
                ),
            )
        )
    return tuple(sources)


def _parse_stages(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ("ingest",)
    if not isinstance(raw, list) or not raw:
        raise PipelineRunConfigError("stages must be a non-empty list when provided")

    stages: list[str] = []
    for i, name in enumerate(raw):
        stage = _require_non_empty_str(name, f"stages[{i}]")
        if stage not in KNOWN_STAGES:
            raise PipelineRunConfigError(
                f"unknown stage {stage!r}; expected one of {KNOWN_STAGES}"
            )
        stages.append(stage)
    return tuple(stages)


def load_run_config(path: Path | str) -> PipelineRunContext:
    """Read a YAML run instance into a PipelineRunContext."""
    config_path = Path(path)
    if not config_path.is_file():
        raise PipelineRunConfigError(f"run config not found: {config_path}")

    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise PipelineRunConfigError("run config root must be a mapping")

    sources = _parse_sources(data.get("sources"))
    stages = _parse_stages(data.get("stages"))

    run_id = data.get("run_id")
    if run_id is not None:
        run_id = _require_non_empty_str(run_id, "run_id")

    stage_args: dict[str, dict] = {}
    for stage in KNOWN_STAGES:
        if stage in data and isinstance(data[stage], dict):
            stage_args[stage] = dict(data[stage])

    progress = data.get("progress", True)
    if not isinstance(progress, bool):
        raise PipelineRunConfigError("progress must be a boolean when provided")

    return PipelineRunContext(
        sources=sources,
        stages=stages,
        run_id=run_id,
        snapshot_raw=bool(data.get("snapshot_raw", False)),
        verbose=bool(data.get("verbose", False)),
        progress=progress,
        stage_args=stage_args,
    )
