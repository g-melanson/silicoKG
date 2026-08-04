"""Context for ontology-driven classification of merged nodes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.paths import DEFAULT_PATHS, REPO_ROOT, UniversePaths

DEFAULT_RULES_PATH = REPO_ROOT / "schemas/ontology/classification-rules.yaml"
DEFAULT_SOURCE_NAME = "obo-so"


@dataclass(frozen=True, kw_only=True)
class ClassifyContext:
    run_id: str
    source_name: str = DEFAULT_SOURCE_NAME
    rules_path: Path = DEFAULT_RULES_PATH
    source: str | None = None
    paths: UniversePaths = DEFAULT_PATHS
