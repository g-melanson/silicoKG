from __future__ import annotations

from pathlib import Path

from pipeline.io.jsonl import dumps_line
from pipeline.transform.engine import TransformSummary, transform_stream
from sources.corum.corum_human_complexes.parse import iter_corum_rows, load_complexes

PKG = Path(__file__).resolve().parents[1]
FIXTURE = PKG / "tests" / "fixtures" / "mini_complexes.json"
SOURCE_SCHEMA = PKG / "corum-human-complexes.schema.yaml"
TRANSFORM = PKG / "corum-human-complexes.transform.yaml"


def _run_transform(tmp_path: Path):
    bronze = tmp_path / "bronze.jsonl"
    rows = list(iter_corum_rows(load_complexes(FIXTURE)))
    bronze.write_bytes(b"".join(dumps_line(r) for r in rows))

    outcomes = []
    summary = None
    for outcome in transform_stream(
        source_row_class="CorumComplexRow",
        bronze_records_path=bronze,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="corum-human-complexes",
    ):
        if isinstance(outcome, TransformSummary):
            summary = outcome
            break
        if outcome.accepted:
            outcomes.append(outcome)
    return outcomes, summary


def _by_type(outcomes, target_class):
    return [o.record for o in outcomes if o.target_class == target_class]


def test_transform_has_no_rejects(tmp_path):
    _outcomes, summary = _run_transform(tmp_path)
    assert summary is not None
    assert summary.rejected_count == 0


def test_protein_complex_node(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    complexes = {r["id"]: r for r in _by_type(outcomes, "ProteinComplex")}
    assert set(complexes) == {"CORUM:1", "CORUM:16", "CORUM:36"}
    c1 = complexes["CORUM:1"]
    assert c1["name"] == "BCL6-HDAC4 complex"
    assert c1["tax_id"] == "NCBITaxon:9606"
    assert c1["class_labels"] == ["silkg:CORUM"]


def test_annotated_evidence_node(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    evidence = {r["id"]: r for r in _by_type(outcomes, "AnnotatedEvidence")}
    ev1 = evidence["silkg:AnnotatedEvidence:corum:1"]
    assert "11929873" in ev1["pubmed_id"]
    assert "22222222" in ev1["pubmed_id"]
    assert ev1["class_labels"] == ["silkg:CORUM"]


def test_has_evidence_edge(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    edges = {r["subject"]: r for r in _by_type(outcomes, "ProteinComplexHasEvidence")}
    edge = edges["CORUM:1"]
    assert edge["object"] == "silkg:AnnotatedEvidence:corum:1"
    assert edge["predicate"] == "silkg:HAS_EVIDENCE"


def test_protein_stub_and_membership(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    proteins = {r["id"]: r for r in _by_type(outcomes, "Protein")}
    assert "silkg:Protein:9606:P41182" in proteins
    assert proteins["silkg:Protein:9606:P41182"]["protein_accession_version"] == "P41182"
    memberships = _by_type(outcomes, "ProteinMemberOfComplex")
    edge = next(m for m in memberships if m["subject"] == "silkg:Protein:9606:P41182")
    assert edge["object"] == "CORUM:1"
    assert edge["predicate"] == "silkg:MEMBER_OF"
    assert edge["id"] == "silkg:ProteinMemberOfComplex:9606:P41182:1"


def test_go_association_edges_use_aspect_predicate(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    go_edges = {
        (r["subject"], r["object"]): r
        for r in _by_type(outcomes, "ProteinComplexGOAssociation")
    }
    mf = go_edges[("CORUM:1", "silkg:MolecularFunction:GO:0004407")]
    assert mf["predicate"] == "silkg:HAS_FUNCTION"
    assert mf["pubmed_id"] == ["11929873"]
    bp = go_edges[("CORUM:1", "silkg:BiologicalProcess:GO:0006265")]
    assert bp["predicate"] == "silkg:PARTICIPATES_IN"
    assert bp["pubmed_id"] == ["22222222"]


def test_fcg_gene_group_and_edges_avoid_id_collision(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    groups = {r["id"]: r for r in _by_type(outcomes, "GeneGroup")}
    assert "CORUM:FCG16" in groups
    # The FCG GeneGroup id must never collide with complex id CORUM:16.
    assert "CORUM:16" not in groups
    assert groups["CORUM:FCG16"]["name"] == "Vesicle-mediated transport"
    assert groups["CORUM:FCG16"]["class_labels"] == ["silkg:CORUM"]

    membership = _by_type(outcomes, "ProteinComplexMemberOfGeneGroup")[0]
    assert membership["subject"] == "CORUM:36"
    assert membership["object"] == "CORUM:FCG16"
    assert membership["predicate"] == "silkg:MEMBER_OF"
    assert membership["pubmed_id"] == ["9733768"]

    broad = _by_type(outcomes, "GeneGroupBroadMatchGO")[0]
    assert broad["subject"] == "CORUM:FCG16"
    assert broad["object"] == "silkg:BiologicalProcess:GO:0016192"
    assert broad["predicate"] == "silkg:BROAD_MATCH"


def test_complex_16_and_fcg_16_are_distinct_nodes(tmp_path):
    outcomes, _ = _run_transform(tmp_path)
    complex_ids = {r["id"] for r in _by_type(outcomes, "ProteinComplex")}
    group_ids = {r["id"] for r in _by_type(outcomes, "GeneGroup")}
    assert "CORUM:16" in complex_ids
    assert "CORUM:FCG16" in group_ids
    assert complex_ids.isdisjoint(group_ids)
