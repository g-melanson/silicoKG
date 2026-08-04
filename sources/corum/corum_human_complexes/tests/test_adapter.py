from __future__ import annotations

from pathlib import Path

from sources.corum.corum_human_complexes.parse import (
    dedupe_pmids,
    go_object_uri,
    iter_corum_rows,
    join_comments,
    load_complexes,
    normalize_synonyms,
)

FIXTURE = Path(__file__).with_name("fixtures") / "mini_complexes.json"


def _rows() -> list[dict]:
    return list(iter_corum_rows(load_complexes(FIXTURE)))


def _by_kind(rows: list[dict], kind: str) -> list[dict]:
    return [r for r in rows if r["row_kind"] == kind]


def test_row_kind_cardinality():
    rows = _rows()
    assert len(_by_kind(rows, "complex")) == 3
    assert len(_by_kind(rows, "subunit")) == 4  # 2 + 1 + 1
    # complex 36 function has an unknown ontology and is dropped.
    assert len(_by_kind(rows, "function")) == 4  # 3 (c1) + 1 (c16) + 0 (c36)
    assert len(_by_kind(rows, "fcg")) == 1


def test_complex_description_drops_null_member_comment():
    complex_1 = next(r for r in _rows() if r["row_kind"] == "complex" and r["complex_id"] == "1")
    # comment_members is null so description is only comment_complex.
    assert complex_1["description"] == (
        "Transcriptional repression by BCL6 recruits histone deacetylases."
    )
    # comment_disease is null too, so evidence == description here.
    assert complex_1["evidence_description"] == complex_1["description"]


def test_evidence_description_includes_disease_and_members():
    complex_16 = next(r for r in _rows() if r["row_kind"] == "complex" and r["complex_id"] == "16")
    assert complex_16["description"] == "complex level note member level note"
    assert complex_16["evidence_description"] == (
        "complex level note member level note linked to a disease"
    )


def test_pubmed_union_and_dedupe():
    complex_1 = next(r for r in _rows() if r["row_kind"] == "complex" and r["complex_id"] == "1")
    # complex pmid + function pmids, deduped, first-seen order.
    assert complex_1["pubmed_ids"] == ["11929873", "22222222"]
    complex_16 = next(r for r in _rows() if r["row_kind"] == "complex" and r["complex_id"] == "16")
    assert complex_16["pubmed_ids"] == ["111", "222"]


def test_synonyms_split_on_semicolon():
    complex_16 = next(r for r in _rows() if r["row_kind"] == "complex" and r["complex_id"] == "16")
    assert complex_16["synonyms"] == ["Alias A", "Alias B"]
    complex_1 = next(r for r in _rows() if r["row_kind"] == "complex" and r["complex_id"] == "1")
    assert complex_1["synonyms"] == []


def test_function_predicate_and_go_uri_by_aspect():
    functions = {(r["complex_id"], r["go_id"]): r for r in _by_kind(_rows(), "function")}
    mf = functions[("1", "GO:0004407")]
    assert mf["predicate"] == "silkg:HAS_FUNCTION"
    assert mf["go_object_uri"] == "silkg:MolecularFunction:GO:0004407"
    cc = functions[("1", "GO:0005634")]
    assert cc["predicate"] == "silkg:ACTIVE_IN"
    assert cc["go_object_uri"] == "silkg:CellComponent:GO:0005634"
    bp = functions[("1", "GO:0006265")]
    assert bp["predicate"] == "silkg:PARTICIPATES_IN"
    assert bp["go_object_uri"] == "silkg:BiologicalProcess:GO:0006265"


def test_unknown_ontology_function_is_dropped():
    functions = _by_kind(_rows(), "function")
    assert not any(f["complex_id"] == "36" for f in functions)


def test_fcg_row_uses_prefixed_id_and_complex_pmid():
    fcg = _by_kind(_rows(), "fcg")[0]
    assert fcg["complex_id"] == "36"
    assert fcg["fcg_id"] == "16"
    assert fcg["go_object_uri"] == "silkg:BiologicalProcess:GO:0016192"
    # membership edge pmid is the complex-level pmid, not the function pmid.
    assert fcg["pubmed_ids"] == ["9733768"]
    assert fcg["class_labels"] == ["silkg:CORUM"]


def test_subunit_stub_fields():
    subunit = next(r for r in _by_kind(_rows(), "subunit") if r["uniprot_id"] == "P41182")
    assert subunit["complex_id"] == "1"
    assert subunit["gene_name"] == "BCL6"
    assert subunit["protein_name"] == "B-cell lymphoma 6 protein"
    assert subunit["tax_id"] == "9606"


def test_join_comments_helper():
    assert join_comments(None, "", "  ") is None
    assert join_comments("a", None, "b") == "a b"


def test_normalize_synonyms_helper():
    assert normalize_synonyms(None) == []
    assert normalize_synonyms("A;B ; C") == ["A", "B", "C"]


def test_dedupe_pmids_helper():
    assert dedupe_pmids([1, "1", "PMID:2", None, "", 2]) == ["1", "2"]


def test_go_object_uri_helper():
    assert go_object_uri("GO:1", "cellular_component") == "silkg:CellComponent:GO:1"
    assert go_object_uri("GO:1", "unknown") is None
    assert go_object_uri(None, "molecular_function") is None
