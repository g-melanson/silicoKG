from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pipeline.identity.dbxrefs import normalize_dbxref, normalize_dbxrefs
from pipeline.identity.uris import (
    accession_type,
    chromosome_has_gene_id,
    chromosome_represented_by_id,
    chromosome_uri,
    gene_has_dbxref_id,
    gene_uri,
    genomic_sequence_maps_gene_id,
    genomic_sequence_uri,
    taxon_uri,
)

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "integrate"
    / "tests"
    / "fixtures"
    / "uri-golden.yaml"
)


@pytest.fixture
def golden():
    with FIXTURES.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_a1bg_uris(golden):
    bronze = golden["bronze"]
    expected = golden["expected"]
    assert gene_uri(bronze["tax_id"], bronze["gene_id"]) == expected["gene_uri"]
    assert chromosome_uri(bronze["tax_id"], bronze["chromosome"]) == expected["chromosome_uri"]
    assert taxon_uri(bronze["tax_id"]) == expected["taxon_uri"]
    assert (
        chromosome_has_gene_id(bronze["tax_id"], bronze["chromosome"], bronze["gene_id"])
        == expected["chromosome_has_gene_uri"]
    )


def test_dbxref_normalization(golden):
    normalized, errors = normalize_dbxrefs(golden["bronze"]["dbxrefs"])
    assert errors == []
    assert normalized == golden["expected"]["normalized_dbxrefs"]


def test_gene_has_dbxref_ids(golden):
    bronze = golden["bronze"]
    normalized, _ = normalize_dbxrefs(bronze["dbxrefs"])
    ids = [gene_has_dbxref_id(bronze["tax_id"], bronze["gene_id"], x) for x in normalized]
    assert ids == golden["expected"]["gene_has_dbxref_ids"]


def test_genomic_sequence_uris():
    assert (
        genomic_sequence_uri("9606", "NC_000019.10")
        == "silkg:GenomicSequence:9606:NC_000019.10"
    )
    assert (
        genomic_sequence_maps_gene_id("9606", "NC_000019.10", "1")
        == "silkg:GenomicSequenceMapsGene:9606:NC_000019.10:1"
    )
    assert (
        chromosome_represented_by_id("9606", "19", "NC_000019.10")
        == "silkg:ChromosomeRepresentedBy:9606:19:NC_000019.10"
    )


def test_accession_type_classification():
    assert accession_type("NC_000019.10") == "chromosome"
    assert accession_type("NG_011717.2") == "gene_scaffold"
    assert accession_type("NW_009646201.1") == "wgs_contig"
    assert accession_type("NT_187633.1") == "clone_contig"
    assert accession_type("AC_000001.1") == "other"
    assert accession_type("") is None
    assert accession_type(None) is None


def test_unparseable_dbxref():
    assert normalize_dbxref("not-a-curie") is None
    normalized, errors = normalize_dbxrefs(["HGNC:HGNC:5", "bad-value"])
    assert normalized == ["HGNC:5"]
    assert len(errors) == 1
