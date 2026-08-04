"""Helpers for GO term node IDs and OWL property labels."""

from __future__ import annotations

from collections.abc import Mapping

ASPECT_TO_CLASS: dict[str, str] = {
    "biological_process": "BiologicalProcess",
    "cellular_component": "CellComponent",
    "molecular_function": "MolecularFunction",
}

# Common RO / BFO / GOREL properties in go.owl restrictions.
PREDICATE_LABELS: dict[str, str] = {
    "BFO:0000050": "part_of",
    "BFO:0000051": "has_part",
    "BFO:0000066": "occurs_in",
    "GOREL:0002003": "occurs_in",
    "RO:0000057": "has_participant",
    "RO:0002007": "has_output",
    "RO:0002162": "in_taxon",
    "RO:0002211": "regulates",
    "RO:0002212": "negatively_regulates",
    "RO:0002213": "positively_regulates",
    "RO:0002215": "capable_of",
    "RO:0002216": "capable_of_part_of",
    "RO:0002296": "causally_upstream_of_or_within",
    "RO:0002297": "causally_upstream_of",
    "RO:0002298": "causally_upstream_of_or_within_negative_effect",
    "RO:0002299": "causally_upstream_of_or_within_positive_effect",
    "RO:0002315": "results_in",
    "RO:0002338": "results_in_development_of",
    "RO:0002339": "results_in_morphology_of",
    "RO:0002342": "results_in_acquisition_of_features_of",
    "RO:0002565": "results_in_movement_of",
    "RO:0002588": "results_in_transport_to",
    "RO:0002592": "results_in_transport_from",
    "RO:0002630": "acts_on_population_of",
    "RO:0004007": "biomarker_for",
    "RO:0004008": "has_input",
    "RO:0004009": "causally_upstream_of",
    "RO:0012003": "acts_on_population_of",
    "RO:0012014": "has_characteristic",
    "RO:0019000": "regulates_characteristic",
}


def _normalize_aspect(aspect: object | None) -> str | None:
    if aspect is None:
        return None
    value = str(aspect)
    if value in ASPECT_TO_CLASS:
        return value
    if "." in value:
        return value.split(".")[-1]
    return value


def go_term_node_id(
    term_id: object | None,
    aspect: object | None = None,
    aspect_map: Mapping[str, str] | None = None,
) -> str | None:
    """Build a silkg GO term node id from a GO CURIE and aspect."""
    if term_id is None:
        return None
    curie = str(term_id)
    if not curie.startswith("GO:"):
        return None
    resolved_aspect = _normalize_aspect(aspect)
    if resolved_aspect is None and aspect_map is not None:
        resolved_aspect = _normalize_aspect(aspect_map.get(curie))
    if resolved_aspect is None:
        return None
    class_name = ASPECT_TO_CLASS.get(resolved_aspect)
    if class_name is None:
        return None
    return f"silkg:{class_name}:{curie}"


def go_predicate_label(predicate_id: object | None) -> str | None:
    """Map an OWL property CURIE to a Neo4j-friendly relationship label."""
    if predicate_id is None:
        return None
    curie = str(predicate_id)
    if curie in PREDICATE_LABELS:
        return PREDICATE_LABELS[curie]
    if ":" not in curie:
        return curie
    prefix, local = curie.split(":", 1)
    return f"{prefix.lower()}_{local.replace('.', '_')}"


def load_go_aspect_map(bronze_records_path) -> dict[str, str]:
    """Scan bronze term rows for GO id -> aspect."""
    import json

    aspect_map: dict[str, str] = {}
    with bronze_records_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("row_kind") != "term":
                continue
            term_id = row.get("term_id")
            aspect = row.get("aspect")
            if term_id and aspect:
                aspect_map[str(term_id)] = str(aspect)
    return aspect_map
