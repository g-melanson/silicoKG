from __future__ import annotations

from pipeline.publish.projection import project_record, validation_payload


def test_project_record_strips_sources():
    merged = {
        "id": "silkg:Gene:9606:1",
        "@type": "Gene",
        "symbol": "A1BG",
        "sources": [{"source_name": "ncbi-gene-info"}],
    }
    projected = project_record(merged)
    assert "sources" not in projected
    assert projected["symbol"] == "A1BG"
    assert projected["@type"] == "Gene"


def test_validation_payload_excludes_runtime_fields():
    merged = {
        "id": "silkg:ChromosomeHasGene:63221:MT:6775062",
        "@type": "ChromosomeHasGene",
        "subject": "silkg:Chromosome:63221:MT",
        "predicate": "silkg:HAS_GENE",
        "object": "silkg:Gene:63221:6775062",
        "sources": [{"source_name": "ncbi-gene-info"}],
    }
    payload = validation_payload(merged)
    assert payload == {
        "id": "silkg:ChromosomeHasGene:63221:MT:6775062",
        "subject": "silkg:Chromosome:63221:MT",
        "object": "silkg:Gene:63221:6775062",
    }
