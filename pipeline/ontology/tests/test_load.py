from __future__ import annotations

from pathlib import Path

from pipeline.ontology.load import _resolve_source
from pipeline.paths import REPO_ROOT


def test_resolve_local_url():
    resolved = _resolve_source("local://data/go-plus.owl")
    assert resolved == REPO_ROOT / "data/go-plus.owl"
    assert isinstance(resolved, Path)


def test_resolve_local_url_does_not_mangle_slashes():
    """Path('local://...') collapses //; _resolve_source must not."""
    resolved = _resolve_source("local://pipeline/ontology/tests/fixtures/minimal-index.yaml")
    assert resolved == REPO_ROOT / "pipeline/ontology/tests/fixtures/minimal-index.yaml"
