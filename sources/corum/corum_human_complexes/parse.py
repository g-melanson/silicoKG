"""Flatten CORUM human complex JSON into typed bronze rows.

One complex object yields multiple rows discriminated by ``row_kind``:
``complex`` (1), ``subunit`` (1 per subunit), ``function`` (1 per GO function),
and ``fcg`` (1 per Functional Complex Group membership). GeneGroup emission for
FCGs is deduplicated here so silver stays quiet.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

TAX_ID = "9606"
CORUM_CLASS_LABELS = ["silkg:CORUM"]

# CORUM go.ontology -> (silkg GO class for URIs, complex->GO predicate CURIE).
ASPECT_TO_GO_CLASS: dict[str, str] = {
    "molecular_function": "MolecularFunction",
    "cellular_component": "CellComponent",
    "biological_process": "BiologicalProcess",
}
ASPECT_TO_PREDICATE: dict[str, str] = {
    "molecular_function": "silkg:HAS_FUNCTION",
    "cellular_component": "silkg:ACTIVE_IN",
    "biological_process": "silkg:PARTICIPATES_IN",
}


def join_comments(*parts: object, sep: str = " ") -> str | None:
    """Join non-empty comment fields; treat JSON null and '' as absent."""
    chunks = [str(p).strip() for p in parts if p is not None and str(p).strip()]
    return sep.join(chunks) or None


def normalize_synonyms(value: object) -> list[str]:
    """CORUM synonyms are null or a single ';'-delimited string."""
    if value is None:
        return []
    parts = [chunk.strip() for chunk in str(value).split(";")]
    return [chunk for chunk in parts if chunk]


def normalize_pmid(value: object) -> str | None:
    """Store PubMed ids as decimal strings without a PMID: prefix."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.removeprefix("PMID:").strip() or None


def dedupe_pmids(values: Iterator[object]) -> list[str]:
    """Deduplicate PubMed ids preserving first-seen order."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for value in values:
        pmid = normalize_pmid(value)
        if pmid and pmid not in seen_set:
            seen_set.add(pmid)
            seen.append(pmid)
    return seen


def go_object_uri(go_id: object, ontology: object) -> str | None:
    """Build a silkg GO term URI from a GO CURIE and CORUM aspect string."""
    if not go_id:
        return None
    go_class = ASPECT_TO_GO_CLASS.get(str(ontology))
    if go_class is None:
        return None
    return f"silkg:{go_class}:{go_id}"


def _complex_id(complex_obj: dict) -> str:
    return str(complex_obj["complex_id"])


def build_complex_row(complex_obj: dict) -> dict:
    description = join_comments(
        complex_obj.get("comment_complex"),
        complex_obj.get("comment_members"),
    )
    evidence_description = join_comments(
        complex_obj.get("comment_complex"),
        complex_obj.get("comment_members"),
        complex_obj.get("comment_disease"),
        complex_obj.get("comment_drug"),
        complex_obj.get("comment_drug_formal"),
    )
    function_pmids = (fn.get("pmid") for fn in complex_obj.get("functions") or [])
    pubmed_ids = dedupe_pmids(
        [complex_obj.get("pmid"), *function_pmids]
    )
    return {
        "row_kind": "complex",
        "complex_id": _complex_id(complex_obj),
        "complex_name": complex_obj.get("complex_name"),
        "synonyms": normalize_synonyms(complex_obj.get("synonyms")),
        "description": description,
        "evidence_description": evidence_description,
        "pubmed_ids": pubmed_ids,
        "tax_id": TAX_ID,
        "class_labels": list(CORUM_CLASS_LABELS),
    }


def build_subunit_rows(complex_obj: dict) -> Iterator[dict]:
    complex_id = _complex_id(complex_obj)
    for subunit in complex_obj.get("subunits") or []:
        swissprot = subunit.get("swissprot") or {}
        uniprot_id = swissprot.get("uniprot_id")
        if not uniprot_id:
            continue
        yield {
            "row_kind": "subunit",
            "complex_id": complex_id,
            "uniprot_id": str(uniprot_id),
            "gene_name": swissprot.get("gene_name"),
            "protein_name": swissprot.get("protein_name"),
            "tax_id": TAX_ID,
        }


def build_function_rows(complex_obj: dict) -> Iterator[dict]:
    complex_id = _complex_id(complex_obj)
    for function in complex_obj.get("functions") or []:
        go = function.get("go") or {}
        go_id = go.get("go_id")
        ontology = go.get("ontology")
        predicate = ASPECT_TO_PREDICATE.get(str(ontology))
        object_uri = go_object_uri(go_id, ontology)
        # Quarantine rows with an unknown GO aspect (no predicate / object URI).
        if not go_id or predicate is None or object_uri is None:
            continue
        yield {
            "row_kind": "function",
            "complex_id": complex_id,
            "go_id": str(go_id),
            "ontology": str(ontology),
            "predicate": predicate,
            "go_object_uri": object_uri,
            "pubmed_ids": dedupe_pmids([function.get("pmid")]),
            "evi": function.get("evi"),
        }


def build_fcg_rows(complex_obj: dict) -> Iterator[dict]:
    complex_id = _complex_id(complex_obj)
    complex_pmids = dedupe_pmids([complex_obj.get("pmid")])
    for fcg_membership in complex_obj.get("fcgs") or []:
        fcg = fcg_membership.get("fcg") or {}
        fcg_id = fcg.get("fcg_id")
        if fcg_id is None:
            continue
        go = fcg.get("go") or {}
        ontology = go.get("ontology")
        yield {
            "row_kind": "fcg",
            "complex_id": complex_id,
            "fcg_id": str(fcg_id),
            "fcg_name": fcg.get("name"),
            "go_id": str(go.get("go_id")) if go.get("go_id") else None,
            "ontology": str(ontology) if ontology is not None else None,
            "go_object_uri": go_object_uri(go.get("go_id"), ontology),
            "pubmed_ids": list(complex_pmids),
            "class_labels": list(CORUM_CLASS_LABELS),
        }


def iter_corum_rows(complexes: list[dict]) -> Iterator[dict]:
    """Yield bronze rows for every complex; human-only, FCG GeneGroup deduped."""
    for complex_obj in complexes:
        if complex_obj.get("organism") not in (None, "Human"):
            continue
        yield build_complex_row(complex_obj)
        yield from build_subunit_rows(complex_obj)
        yield from build_function_rows(complex_obj)
        yield from build_fcg_rows(complex_obj)


def load_complexes(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
