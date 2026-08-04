"""Canonical silicoKG URI minting."""

from __future__ import annotations


def taxon_uri(tax_id: str) -> str:
    return f"NCBITaxon:{tax_id}"


def gene_uri(tax_id: str, gene_id: str) -> str:
    return f"silkg:Gene:{tax_id}:{gene_id}"


def gene_group_uri(family_id: str) -> str:
    return f"silkg:GeneGroup:hgnc:{family_id}"


def chromosome_uri(tax_id: str, chromosome: str) -> str:
    return f"silkg:Chromosome:{tax_id}:{chromosome}"


def chromosome_has_gene_id(tax_id: str, chromosome: str, gene_id: str) -> str:
    return f"silkg:ChromosomeHasGene:{tax_id}:{chromosome}:{gene_id}"


def genomic_sequence_uri(tax_id: str, accession: str) -> str:
    return f"silkg:GenomicSequence:{tax_id}:{accession}"


def genomic_sequence_maps_gene_id(tax_id: str, accession: str, gene_id: str) -> str:
    return f"silkg:GenomicSequenceMapsGene:{tax_id}:{accession}:{gene_id}"


def chromosome_represented_by_id(tax_id: str, chromosome: str, accession: str) -> str:
    return f"silkg:ChromosomeRepresentedBy:{tax_id}:{chromosome}:{accession}"


def accession_type(accession: str | None) -> str | None:
    """Classify a RefSeq genomic accession by its prefix.

    NC_ -> chromosome, NG_ -> gene_scaffold, NW_ -> wgs_contig,
    NT_ -> clone_contig; anything else -> other. Returns None for empty input.
    """
    if not accession:
        return None
    prefix_map = {
        "NC_": "chromosome",
        "NG_": "gene_scaffold",
        "NW_": "wgs_contig",
        "NT_": "clone_contig",
    }
    for prefix, kind in prefix_map.items():
        if accession.startswith(prefix):
            return kind
    return "other"


def gene_has_dbxref_id(tax_id: str, gene_id: str, normalized_xref: str) -> str:
    safe_xref = normalized_xref.replace(":", "_")
    return f"silkg:GeneHasDbXref:{tax_id}:{gene_id}:{safe_xref}"
