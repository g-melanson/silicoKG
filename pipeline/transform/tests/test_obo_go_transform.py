from __future__ import annotations

import json
from pathlib import Path

from pipeline.ontology.go_uri import go_predicate_label, go_term_node_id, load_go_aspect_map
from pipeline.transform.engine import TransformSummary, transform_stream

REPO = Path(__file__).resolve().parents[3]
SOURCE_SCHEMA = REPO / "sources/obo/go/obo-go.schema.yaml"
TRANSFORM = REPO / "sources/obo/go/obo-go.transform.yaml"


def test_go_predicate_label_maps_common_properties():
    assert go_predicate_label("BFO:0000050") == "part_of"
    assert go_predicate_label("RO:0002211") == "regulates"
    assert go_predicate_label("RO:0009999") == "ro_0009999"


def test_go_term_node_id_uses_aspect_map():
    aspect_map = {
        "GO:0000015": "biological_process",
        "GO:0005829": "cellular_component",
    }
    assert go_term_node_id("GO:0000015", None, aspect_map) == (
        "silkg:BiologicalProcess:GO:0000015"
    )
    assert go_term_node_id("GO:0005829", None, aspect_map) == (
        "silkg:CellComponent:GO:0005829"
    )


def test_obo_go_transform_emits_object_property_edge(tmp_path):
    bronze_path = tmp_path / "bronze.jsonl"
    rows = [
        {
            "row_kind": "term",
            "term_id": "GO:0000015",
            "iri": "http://purl.obolibrary.org/obo/GO_0000015",
            "label": "transcription initiation at RNA polymerase I promoter",
            "aspect": "biological_process",
        },
        {
            "row_kind": "term",
            "term_id": "GO:0005829",
            "iri": "http://purl.obolibrary.org/obo/GO_0005829",
            "label": "cytosol",
            "aspect": "cellular_component",
        },
        {
            "row_kind": "edge",
            "subject_id": "GO:0000015",
            "subject_aspect": "biological_process",
            "predicate_id": "BFO:0000050",
            "object_id": "GO:0005829",
            "object_aspect": "cellular_component",
        },
        {
            "row_kind": "edge",
            "subject_id": "GO:0000015",
            "subject_aspect": "biological_process",
            "predicate_id": "rdfs:subClassOf",
            "object_id": "GO:0005829",
        },
        {
            "row_kind": "edge",
            "subject_id": "GO:0000015",
            "subject_aspect": "biological_process",
            "predicate_id": "RO:0002162",
            "object_id": "NCBITaxon:9606",
        },
    ]
    with bronze_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    fragments = []
    summary = None
    for outcome in transform_stream(
        source_row_class="GOTermRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="obo-go",
    ):
        if isinstance(outcome, TransformSummary):
            summary = outcome
        else:
            fragments.append(outcome)

    object_props = [
        o for o in fragments if o.accepted and o.target_class == "GOObjectPropertyEdge"
    ]
    is_a = [o for o in fragments if o.accepted and o.target_class == "GOIsA"]
    assert len(object_props) == 1
    assert len(is_a) == 1
    edge = object_props[0].record
    assert edge["predicate"] == "part_of"
    assert edge["predicate_id"] == "BFO:0000050"
    assert edge["subject"] == "silkg:BiologicalProcess:GO:0000015"
    assert edge["object"] == "silkg:CellComponent:GO:0005829"
    assert summary is not None
    assert summary.rejected_count == 0


def test_load_go_aspect_map(tmp_path):
    bronze_path = tmp_path / "bronze.jsonl"
    bronze_path.write_text(
        json.dumps(
            {
                "row_kind": "term",
                "term_id": "GO:0008150",
                "iri": "http://purl.obolibrary.org/obo/GO_0008150",
                "label": "biological_process",
                "aspect": "biological_process",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert load_go_aspect_map(bronze_path) == {"GO:0008150": "biological_process"}
