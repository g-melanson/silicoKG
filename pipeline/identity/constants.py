"""Identity contract constants."""

EDGE_CLASS_TO_PREDICATE: dict[str, str] = {
    "ChromosomeHasGene": "silkg:HAS_GENE",
    "GenomicSequenceMapsGene": "silkg:MAPS_TO",
    "ChromosomeRepresentedBy": "silkg:REPRESENTED_BY",
    "GeneHasDbXref": "silkg:SAME_AS",
    "ProteinSameAs": "silkg:SAME_AS",
    "ProteinSameAsProtein": "silkg:SAME_AS",
    "TranscriptSameAsTranscript": "silkg:SAME_AS",
    "GeneHasTranscript": "silkg:HAS_TRANSCRIPT",
    "GeneHasPseudogene": "silkg:PSEUDOGENE",
    "GeneHasReadthroughParent": "silkg:READTHROUGH_PARENT",
    "GeneHasReadthroughSibling": "silkg:READTHROUGH_SIBLING",
    "GeneHasRegionParent": "silkg:REGION_PARENT",
    "GeneSameAsGene": "silkg:SAME_AS",
    "GeneHasTranscriptProduct": "silkg:HAS_TRANSCRIPT_PRODUCT",
    "TranscriptHasProteinProduct": "silkg:HAS_PROTEIN_PRODUCT",
    "ProteinHasMaturePeptideProduct": "silkg:HAS_MATURE_PEPTIDE_PRODUCT",
    # Legacy aliases
    "GeneHasProductTranscript": "silkg:HAS_TRANSCRIPT_PRODUCT",
    "TranscriptHasProductProtein": "silkg:HAS_PROTEIN_PRODUCT",
    "ProteinHasProductMaturePeptide": "silkg:HAS_MATURE_PEPTIDE_PRODUCT",
    "TFInteractsWithGene": "silkg:INTERACTS_WITH",
    "GOIsA": "silkg:SUBCLASS_OF",
    "GeneGroupBroaderThan": "silkg:SUBCLASS_OF",
    "GeneMemberOfGeneGroup": "silkg:MEMBER_OF",
    # CORUM protein complexes
    "ProteinMemberOfComplex": "silkg:MEMBER_OF",
    "ProteinComplexHasEvidence": "silkg:HAS_EVIDENCE",
    "ProteinComplexMemberOfGeneGroup": "silkg:MEMBER_OF",
    "GeneGroupBroadMatchGO": "silkg:BROAD_MATCH",
}

EDGE_CLASSES = frozenset(EDGE_CLASS_TO_PREDICATE)

MULTIVALUED_NODE_SLOTS = frozenset(
    {
        "synonyms",
        "dbxrefs",
        "same_as",
        "sources",
        "alternates",
        "feature_types",
        "so_types",
        "so_qualities",
        "class_labels",
        "pubmed_id",
    }
)

RESERVED_NODE_KEYS = frozenset({"id", "@type", "sources", "alternates"})
