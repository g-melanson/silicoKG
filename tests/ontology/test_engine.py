from __future__ import annotations

import pytest

from pipeline.ontology.context import OntologyContext
from pipeline.ontology.engine import iri_to_curie


def _ctx(**overrides) -> OntologyContext:
    defaults = {
        "url": "http://example.org/test.owl",
        "source": "obo",
        "source_name": "test",
        "ontology_namespace": "http://purl.obolibrary.org/obo/GO_",
        "term_id_prefix": "GO",
    }
    defaults.update(overrides)
    return OntologyContext(**defaults)


def test_iri_to_curie_primary_namespace():
    ctx = _ctx()
    assert iri_to_curie("http://purl.obolibrary.org/obo/GO_0008150", ctx) == "GO:0008150"


def test_iri_to_curie_property_namespace():
    ctx = _ctx(
        ontology_namespace="http://purl.obolibrary.org/obo/SO_",
        term_id_prefix="SO",
        property_namespace="http://purl.obolibrary.org/obo/so#",
        property_id_prefix="so",
    )
    assert iri_to_curie("http://purl.obolibrary.org/obo/so#has_quality", ctx) == "so:has_quality"


def test_iri_to_curie_obo_fallback_for_cross_namespace_refs():
    ctx = _ctx()
    assert iri_to_curie("http://purl.obolibrary.org/obo/GOREL_0002003", ctx) == "GOREL:0002003"
    assert iri_to_curie("http://purl.obolibrary.org/obo/RO_0000057", ctx) == "RO:0000057"
    assert iri_to_curie("http://purl.obolibrary.org/obo/CHEBI_15377", ctx) == "CHEBI:15377"
    assert (
        iri_to_curie("http://purl.obolibrary.org/obo/NCBITaxon_Union_117568", ctx)
        == "NCBITaxon:Union_117568"
    )


def test_iri_to_curie_rejects_unknown_namespace():
    ctx = _ctx()
    with pytest.raises(ValueError, match="unexpected IRI namespace"):
        iri_to_curie("http://example.org/unknown", ctx)


def test_object_property_rows_from_subclass_restriction():
    from rdflib import Graph, URIRef

    from pipeline.ontology.engine import object_property_rows, term_taxonomy_rows

    ttl = """
    @prefix GO: <http://purl.obolibrary.org/obo/GO_> .
    @prefix RO: <http://purl.obolibrary.org/obo/RO_> .
    @prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    GO:0006915 a owl:Class ;
        oboInOwl:hasOBONamespace "biological_process" ;
        rdfs:subClassOf GO:0008150 ;
        rdfs:subClassOf [
            a owl:Restriction ;
            owl:onProperty RO:0002211 ;
            owl:someValuesFrom GO:0008150
        ] .

    GO:0008150 a owl:Class ;
        oboInOwl:hasOBONamespace "biological_process" .
    """
    graph = Graph()
    graph.parse(data=ttl, format="ttl")
    ctx = _ctx()
    term = URIRef("http://purl.obolibrary.org/obo/GO_0006915")

    is_a = list(term_taxonomy_rows(graph, term, ctx))
    assert len(is_a) == 1
    assert is_a[0].predicate_id == "rdfs:subClassOf"
    assert is_a[0].object_id == "GO:0008150"

    relations = list(object_property_rows(graph, term, ctx))
    assert len(relations) == 1
    assert relations[0].predicate_id == "RO:0002211"
    assert relations[0].object_id == "GO:0008150"
    assert relations[0].subject_aspect is not None
    assert str(relations[0].subject_aspect) == "biological_process"
    assert relations[0].object_aspect is not None
    assert str(relations[0].object_aspect) == "biological_process"


def test_class_row_reads_obo_namespace_aspect():
    from rdflib import Graph, URIRef

    from pipeline.ontology.engine import class_row

    ttl = """
    @prefix GO: <http://purl.obolibrary.org/obo/GO_> .
    @prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    GO:0008150 a owl:Class ;
        rdfs:label "biological process" ;
        oboInOwl:hasOBONamespace "biological_process" .
    """
    graph = Graph()
    graph.parse(data=ttl, format="ttl")
    ctx = _ctx()
    term = URIRef("http://purl.obolibrary.org/obo/GO_0008150")

    row = class_row(graph, term, ctx)
    assert str(row.aspect) == "biological_process"
