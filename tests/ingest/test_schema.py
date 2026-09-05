from __future__ import annotations

from pathlib import Path

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin

from pipeline.ingest.schema import load_merged_schema, load_source_schema, multivalued_delimiters
from pipeline.paths import REPO_ROOT

GENE_INFO_SCHEMA = REPO_ROOT / "sources/ncbi/ncbi_gene_info/ncbi-gene-info.schema.yaml"
OBO_GO_SCHEMA = REPO_ROOT / "sources/obo/go/obo-go.schema.yaml"


def test_load_merged_schema_strips_delimiter_extension():
    schema = load_merged_schema(GENE_INFO_SCHEMA)
    assert "NCBIGeneInfoRow" in schema["classes"]
    attrs = schema["classes"]["NCBIGeneInfoRow"]["attributes"]
    assert "delimiter" not in attrs["synonyms"]
    assert attrs["synonyms"]["multivalued"] is True


def test_load_source_schema_keeps_delimiters_for_ingest():
    schema = load_source_schema(GENE_INFO_SCHEMA)
    delimiters = multivalued_delimiters(schema, target_class="NCBIGeneInfoRow")
    assert delimiters["synonyms"] == "|"
    assert delimiters["dbxrefs"] == "|"


def test_merged_schema_loads_in_linkml_validator():
    schema = load_merged_schema(GENE_INFO_SCHEMA)
    Validator(schema, validation_plugins=[JsonschemaValidationPlugin(closed=True)])


def test_merged_schema_inlines_imported_classes():
    schema = load_merged_schema(OBO_GO_SCHEMA)
    assert "imports" not in schema
    assert "GOTermRow" in schema["classes"]
    assert "OntologyTermRow" in schema["classes"]
    Validator(schema, validation_plugins=[JsonschemaValidationPlugin(closed=True)])
