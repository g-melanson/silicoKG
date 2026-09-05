from __future__ import annotations

from pipeline.paths import REPO_ROOT
from pipeline.transform.engine import TransformSummary, transform_stream
from sources.uniprot.gaf.adapter import UniProtGafAdapter

GAF_FIXTURE = REPO_ROOT / "fixtures/uniprot/HUMAN-uniprot.small.gaf"
SOURCE_SCHEMA = REPO_ROOT / "sources/uniprot/gaf/uniprot-gaf.schema.yaml"
TRANSFORM = REPO_ROOT / "sources/uniprot/gaf/uniprot-gaf.transform.yaml"


def test_gaf_adapter_parses_relation_and_negated(tmp_path):
    adapter = UniProtGafAdapter()
    rows = list(adapter.parse(GAF_FIXTURE))
    assert rows
    assert rows[0]["relation"] == "enables"
    assert rows[0]["negated"] is False
    assert rows[0]["db_object_id"] == "A0A024RBG1"
    assert rows[0]["go_id"] == "GO:0005515"


def test_gaf_transform_emits_passthrough_predicate(tmp_path):
    adapter = UniProtGafAdapter()
    bronze_path = tmp_path / "bronze.jsonl"
    import json

    with bronze_path.open("w", encoding="utf-8") as handle:
        for row in adapter.parse(GAF_FIXTURE):
            handle.write(json.dumps(row) + "\n")

    fragments = []
    summary = None
    for outcome in transform_stream(
        source_row_class="UniProtGafRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="uniprot-gaf",
    ):
        if isinstance(outcome, TransformSummary):
            summary = outcome
        else:
            fragments.append(outcome)

    edges = [
        o
        for o in fragments
        if o.accepted and o.target_class == "GeneProductGOAssociationEdge"
    ]
    proteins = [
        o for o in fragments if o.accepted and o.target_class == "Protein"
    ]
    assert edges
    assert proteins
    obj = edges[0].record
    assert obj["predicate"] == "enables"
    assert obj["subject"] == "silkg:Protein:9606:A0A024RBG1"
    assert obj["object"] == "silkg:MolecularFunction:GO:0005515"
    protein = proteins[0].record
    assert protein["id"] == "silkg:Protein:9606:A0A024RBG1"
    assert protein["symbol"] == "NUDT4B"
    assert protein["name"] == (
        "Diphosphoinositol polyphosphate phosphohydrolase NUDT4B"
    )
    assert protein["tax_id"] == "NCBITaxon:9606"
    assert summary is not None
    assert summary.accepted_count >= len(edges) + len(proteins)
