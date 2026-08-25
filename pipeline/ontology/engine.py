"""Extract OWL classes and restrictions as bronze row objects."""

from __future__ import annotations

import re
from collections.abc import Iterator

from rdflib import BNode, Graph, OWL, RDF, RDFS, URIRef
from rdflib.namespace import Namespace

from pipeline.ontology.adapters import (
    BronzeRowKind,
    OntologyTermRow,
    OntologyEdgeRow,
    GOAspects,
)
from pipeline.ontology.context import OntologyContext

GO_NS = "http://purl.obolibrary.org/obo/GO_"
OBOINOWL = Namespace("http://www.geneontology.org/formats/oboInOwl#")
SYNONYM_PROPERTIES = (
    OBOINOWL.hasExactSynonym,
    OBOINOWL.hasRelatedSynonym,
    OBOINOWL.hasBroadSynonym,
    OBOINOWL.hasNarrowSynonym,
)

_OBO_TERM_IRI = re.compile(
    r"^http://purl\.obolibrary\.org/obo/([A-Z][A-Za-z0-9]*)_(.+)$"
)
_IS_A_PREDICATE = "rdfs:subClassOf"
# SO (and other OBO) terms may use hasOBONamespace values outside GO aspects.
_GO_ASPECT_VALUES = frozenset(
    {"biological_process", "cellular_component", "molecular_function"}
)


def _optional_go_aspect(value: object | None) -> GOAspects | None:
    if value is None:
        return None
    text = str(value)
    if text not in _GO_ASPECT_VALUES:
        return None
    return GOAspects(text)


def iter_ontology_terms(
    graph: Graph,
    ctx: OntologyContext,
    terms: list[URIRef] | None = None,
) -> Iterator[OntologyTermRow | OntologyEdgeRow]:
    if terms:
        for term in terms:
            yield from rows_for_term(graph, term, ctx)
        return

    for term in graph.subjects(RDF.type, OWL.Class):
        if isinstance(term, URIRef) and str(term).startswith(ctx.ontology_namespace):
            yield from rows_for_term(graph, term, ctx)

def rows_for_term(graph: Graph, term: URIRef, ctx: OntologyContext) -> list[OntologyTermRow | OntologyEdgeRow]:
    return [
        class_row(graph, term, ctx), 
        *object_property_rows(graph, term, ctx),
        *term_taxonomy_rows(graph, term, ctx)
        ]

def term_taxonomy_rows(graph: Graph, term: URIRef, ctx: OntologyContext) -> Iterator[OntologyEdgeRow]:
    subject_id = iri_to_curie(str(term), ctx)
    aspect = graph.value(term, OBOINOWL.hasOBONamespace)
    for parent in graph.objects(term, RDFS.subClassOf):
        if not isinstance(parent, URIRef):
            continue
        try:
            object_id = iri_to_curie(str(parent), ctx)
        except ValueError:
            continue
        yield OntologyEdgeRow(
            row_kind=BronzeRowKind.edge,
            subject_id=subject_id,
            subject_aspect=_optional_go_aspect(aspect),
            predicate_id=_IS_A_PREDICATE,
            object_id=object_id,
        )


def object_property_rows(graph: Graph, term: URIRef, ctx: OntologyContext) -> Iterator[OntologyEdgeRow]:
    """Extract term-to-term edges from owl:Restriction nodes on rdfs:subClassOf."""
    subject_id = iri_to_curie(str(term), ctx)
    subject_aspect_val = graph.value(term, OBOINOWL.hasOBONamespace)
    subject_aspect = _optional_go_aspect(subject_aspect_val)
    for parent in graph.objects(term, RDFS.subClassOf):
        if not isinstance(parent, BNode):
            continue

        prop = graph.value(parent, OWL.onProperty)
        filler = graph.value(parent, OWL.someValuesFrom)
        if prop is None or filler is None or not isinstance(filler, URIRef):
            continue

        try:
            predicate_id = iri_to_curie(str(prop), ctx)
            object_id = iri_to_curie(str(filler), ctx)
        except ValueError:
            continue

        object_aspect = None
        if str(filler).startswith(ctx.ontology_namespace):
            object_aspect_val = graph.value(filler, OBOINOWL.hasOBONamespace)
            object_aspect = _optional_go_aspect(object_aspect_val)

        yield OntologyEdgeRow(
            row_kind=BronzeRowKind.edge,
            subject_id=subject_id,
            subject_aspect=subject_aspect,
            predicate_id=predicate_id,
            object_id=object_id,
            object_aspect=object_aspect,
        )

def class_row(graph: Graph, term: URIRef, ctx: OntologyContext) -> OntologyTermRow:
    """Build an OntologyClassRow from rdfs/oboInOwl triples."""
    aspect = graph.value(term, OBOINOWL.hasOBONamespace)
    iri = str(term)
    label = str(graph.value(term, RDFS.label) or "")
    synonyms = sorted(
        str(synonym)
        for syn_prop in SYNONYM_PROPERTIES
        for synonym in graph.objects(term, syn_prop)
    )

    return OntologyTermRow(
        row_kind=BronzeRowKind("term"),
        term_id=iri_to_curie(iri, ctx),
        iri=iri,
        label=str(label or ""),
        synonyms=synonyms,
        aspect=_optional_go_aspect(aspect),
    )


def iri_to_curie(iri: str, ctx: OntologyContext) -> str:
    """Map class/property IRIs to the CURIE forms used in bronze rows."""
    if iri.startswith(ctx.ontology_namespace):
        return f"{ctx.term_id_prefix}:{iri.removeprefix(ctx.ontology_namespace)}"
    if (
        ctx.property_namespace
        and ctx.property_id_prefix
        and iri.startswith(ctx.property_namespace)
    ):
        return f"{ctx.property_id_prefix}:{iri.removeprefix(ctx.property_namespace)}"
    match = _OBO_TERM_IRI.match(iri)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    raise ValueError(f"unexpected IRI namespace: {iri}")
