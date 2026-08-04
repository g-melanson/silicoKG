"""Canonical URI minting, dbxref normalization, and edge classification."""

from pipeline.identity.constants import (
    EDGE_CLASS_TO_PREDICATE,
    EDGE_CLASSES,
    MULTIVALUED_NODE_SLOTS,
)
from pipeline.identity.dbxrefs import normalize_dbxref, normalize_dbxrefs
from pipeline.identity.uris import (
    gene_has_dbxref_id,
    gene_uri,
    chromosome_has_gene_id,
    chromosome_uri,
    taxon_uri,
)

__all__ = [
    "EDGE_CLASS_TO_PREDICATE",
    "EDGE_CLASSES",
    "MULTIVALUED_NODE_SLOTS",
    "chromosome_has_gene_id",
    "chromosome_uri",
    "gene_has_dbxref_id",
    "gene_uri",
    "normalize_dbxref",
    "normalize_dbxrefs",
    "taxon_uri",
]
