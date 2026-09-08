"""Staging record builders for validate tests (ncbi-gene-info)."""

from __future__ import annotations


def ncbi_gene_info_row(**overrides: object) -> dict:
    """Minimal valid NCBIGeneInfoRow; pass keyword overrides for test-specific fields."""
    row = {
        "tax_id": "9606",
        "gene_id": "1",
        "symbol": "TEST",
        "locus_tag": None,
        "synonyms": [],
        "dbxrefs": [],
        "chromosome": "1",
        "map_location": "1p",
        "description": "test gene",
        "type_of_gene": "protein-coding",
        "symbol_from_nomenclature_authority": "TEST",
        "full_name_from_nomenclature_authority": "test gene",
        "nomenclature_status": "O",
        "other_designations": [],
        "modification_date": "20260101",
        "feature_type": None,
        "all_synonyms": ["TEST"],
    }
    row.update(overrides)
    return row


def build_valid_staging_records() -> list[dict]:
    return [
        ncbi_gene_info_row(
            gene_id="623",
            symbol="BDKRB1",
            synonyms=["B1BKR", "B1R", "BKB1R", "BKR1", "BRADYB1"],
            dbxrefs=[
                "MIM:600337",
                "HGNC:HGNC:1029",
                "Ensembl:ENSG00000100739",
                "AllianceGenome:HGNC:1029",
            ],
            chromosome="14",
            map_location="14q32.2",
            description="bradykinin receptor B1",
            symbol_from_nomenclature_authority="BDKRB1",
            full_name_from_nomenclature_authority="bradykinin receptor B1",
            other_designations=[
                "B1 bradykinin receptor",
                "BK-1 receptor",
                "bradykinin B1 receptor",
                "bradykinin receptor 1",
            ],
            modification_date="20260706",
            all_synonyms=[
                "BDKRB1",
                "B1BKR",
                "B1R",
                "BKB1R",
                "BKR1",
                "BRADYB1",
                "bradykinin receptor B1",
                "B1 bradykinin receptor",
                "BK-1 receptor",
                "bradykinin B1 receptor",
                "bradykinin receptor 1",
            ],
        ),
        ncbi_gene_info_row(
            gene_id="1082",
            symbol="CGB3",
            synonyms=["CG-beta", "CGB"],
            dbxrefs=[
                "MIM:118860",
                "HGNC:HGNC:1886",
                "Ensembl:ENSG00000104827",
                "AllianceGenome:HGNC:1886",
            ],
            chromosome="19",
            map_location="19q13.33",
            description="chorionic gonadotropin subunit beta 3",
            symbol_from_nomenclature_authority="CGB3",
            full_name_from_nomenclature_authority="chorionic gonadotropin subunit beta 3",
            other_designations=[
                "choriogonadotropin subunit beta 3",
                "chorionic gonadotrophin chain beta",
                "chorionic gonadotropin beta 3 subunit",
                "chorionic gonadotropin beta chain",
                "chorionic gonadotropin beta subunit 3",
                "chorionic gonadotropin chain beta",
                "chorionic gonadotropin, beta polypeptide",
            ],
            modification_date="20260706",
            all_synonyms=[
                "CGB3",
                "CG-beta",
                "CGB",
                "chorionic gonadotropin subunit beta 3",
                "choriogonadotropin subunit beta 3",
                "chorionic gonadotrophin chain beta",
                "chorionic gonadotropin beta 3 subunit",
                "chorionic gonadotropin beta chain",
                "chorionic gonadotropin beta subunit 3",
                "chorionic gonadotropin chain beta",
                "chorionic gonadotropin, beta polypeptide",
            ],
        ),
        ncbi_gene_info_row(
            gene_id="1083",
            symbol="CGF1",
            dbxrefs=["MIM:300082"],
            chromosome="X",
            map_location="Xp11.22-qter",
            description="cognitive function 1, social",
            type_of_gene="unknown",
            symbol_from_nomenclature_authority=None,
            full_name_from_nomenclature_authority=None,
            nomenclature_status=None,
            modification_date="20241207",
            all_synonyms=["CGF1"],
        ),
    ]


def build_missing_property_record() -> list[dict]:
    return [
        ncbi_gene_info_row(
            gene_id="2017",
            symbol="CTTN",
            synonyms=["EMS1"],
            dbxrefs=[
                "MIM:164765",
                "HGNC:HGNC:3338",
                "Ensembl:ENSG00000085733",
                "AllianceGenome:HGNC:3338",
            ],
            chromosome=None,
            map_location="11q13.3",
            description="cortactin",
            symbol_from_nomenclature_authority="CTTN",
            full_name_from_nomenclature_authority="cortactin",
            other_designations=[
                "src substrate cortactin",
                "amplaxin",
                "ems1 sequence (mammary tumor and squamous cell carcinoma-associated (p80/85 src substrate)",
                "epididymis secretory sperm binding protein",
                "oncogene EMS1",
            ],
            modification_date="20260723",
            all_synonyms=[
                "CTTN",
                "EMS1",
                "cortactin",
                "src substrate cortactin",
                "amplaxin",
                "ems1 sequence (mammary tumor and squamous cell carcinoma-associated (p80/85 src substrate)",
                "epididymis secretory sperm binding protein",
                "oncogene EMS1",
            ],
        )
    ]


def build_mutated_property_record() -> list[dict]:
    return [
        ncbi_gene_info_row(
            gene_id="2133",
            symbol="EXT3",
            synonyms="EXT2",
            dbxrefs=["MIM:600209"],
            chromosome="19",
            map_location="19p",
            description="exostoses (multiple) 3",
            type_of_gene="unknown",
            symbol_from_nomenclature_authority=None,
            full_name_from_nomenclature_authority=None,
            nomenclature_status=None,
            modification_date="20241207",
            all_synonyms=["EXT3", "EXT2"],
        )
    ]


def build_misnamed_property_record() -> list[dict]:
    row = ncbi_gene_info_row(
        gene_id="2150",
        symbol="F2RL1",
        synonyms=["GPR11", "PAR2"],
        dbxrefs=[
            "MIM:600933",
            "HGNC:HGNC:3538",
            "Ensembl:ENSG00000164251",
            "AllianceGenome:HGNC:3538",
        ],
        chromosome="5",
        map_location="5q13.3",
        description="F2R like trypsin receptor 1",
        symbol_from_nomenclature_authority="F2RL1",
        full_name_from_nomenclature_authority="F2R like trypsin receptor 1",
        other_designations=[
            "proteinase-activated receptor 2",
            "G-protein coupled receptor 11",
            "coagulation factor II (thrombin) receptor-like 1",
            "protease-activated receptor 2",
            "thrombin receptor-like 1",
        ],
        modification_date="20260723",
        all_synonyms=[
            "F2RL1",
            "GPR11",
            "PAR2",
            "F2R like trypsin receptor 1",
            "proteinase-activated receptor 2",
            "G-protein coupled receptor 11",
            "coagulation factor II (thrombin) receptor-like 1",
            "protease-activated receptor 2",
            "thrombin receptor-like 1",
        ],
    )
    del row["symbol"]
    row["name"] = "F2RL1"
    return [row]


def build_staging_set() -> list[dict]:
    return (
        build_valid_staging_records()
        + build_missing_property_record()
        + build_mutated_property_record()
        + build_misnamed_property_record()
    )
