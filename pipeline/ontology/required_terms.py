"""Collect SO class IRIs required by classification rules and label maps."""

from __future__ import annotations

from pathlib import Path

from pipeline.export.neo4j.label_map import DEFAULT_LABEL_MAP_PATH, load_label_map
from pipeline.ontology.classify.engine import _collect_required_classes
from pipeline.ontology.classify.rules import load_rules
from pipeline.paths import REPO_ROOT


def _resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def collect_required_curie_iris(
    *,
    rules_path: Path,
    label_map_path: Path | None = None,
) -> frozenset[str]:
    """Return SO CURIEs referenced by rules and optional Neo4j label map."""
    curies = set(_collect_required_classes(load_rules(_resolve_repo_path(rules_path))))

    map_path = _resolve_repo_path(label_map_path or DEFAULT_LABEL_MAP_PATH)
    if map_path.is_file():
        label_map = load_label_map(map_path)
        for curie_map in label_map.additional_labels.values():
            curies.update(curie_map)

    return frozenset(curies)


def curies_to_iris(
    curies: frozenset[str],
    *,
    ontology_namespace: str,
    term_id_prefix: str,
) -> frozenset[str]:
    """Convert prefixed CURIEs to ontology class IRIs."""
    prefix = f"{term_id_prefix}:"
    iris: set[str] = set()
    for curie in curies:
        if not curie.startswith(prefix):
            continue
        local_id = curie.removeprefix(prefix)
        iris.add(f"{ontology_namespace}{local_id}")
    return frozenset(iris)


def collect_required_term_iris(
    *,
    rules_path: Path,
    label_map_path: Path | None = None,
    ontology_namespace: str,
    term_id_prefix: str,
) -> frozenset[str]:
    """Return class IRIs to extract when building a scoped ontology index."""
    curies = collect_required_curie_iris(
        rules_path=rules_path,
        label_map_path=label_map_path,
    )
    return curies_to_iris(
        curies,
        ontology_namespace=ontology_namespace,
        term_id_prefix=term_id_prefix,
    )
