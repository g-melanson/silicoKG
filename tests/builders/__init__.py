"""Test record builders with keyword overrides for pipeline stage tests."""

from tests.builders.silver import (
    BRONZE_RECORD,
    GENE_ID,
    GENOMIC_SEQUENCE_ID,
    MAPS_GENE_EDGE_ID,
    SILVER_RUN_ID,
    gene_fragment,
    maps_gene_fragment,
)
from tests.builders.staging import (
    build_misnamed_property_record,
    build_missing_property_record,
    build_mutated_property_record,
    build_staging_set,
    build_valid_staging_records,
    ncbi_gene_info_row,
)

__all__ = [
    "BRONZE_RECORD",
    "GENE_ID",
    "GENOMIC_SEQUENCE_ID",
    "MAPS_GENE_EDGE_ID",
    "SILVER_RUN_ID",
    "build_misnamed_property_record",
    "build_missing_property_record",
    "build_mutated_property_record",
    "build_staging_set",
    "build_valid_staging_records",
    "gene_fragment",
    "maps_gene_fragment",
    "ncbi_gene_info_row",
]
