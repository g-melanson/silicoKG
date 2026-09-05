from __future__ import annotations

from pathlib import Path
from pipeline.transform.runner import _concat_parts, _line_ranges, _worker_shard
from pipeline.io.jsonl import dumps_line
from pipeline.paths import REPO_ROOT
from pipeline.transform.engine import (
    TransformSummary,
    parse_ncbi_feature_types,
    transform_stream,
    transform_bronze_record,
)

BRONZE = REPO_ROOT / "universe/test-small/2-bronze/ncbi-gene-info/records.jsonl"
SOURCE_SCHEMA = REPO_ROOT / "sources/ncbi/ncbi_gene_info/ncbi-gene-info.schema.yaml"
TRANSFORM = REPO_ROOT / "sources/ncbi/ncbi_gene_info/ncbi-gene-info.transform.yaml"
GENE2REFSEQ_BRONZE = REPO_ROOT / "universe/test-x/2-bronze/ncbi-gene2refseq/records.jsonl"
GENE2REFSEQ_SOURCE_SCHEMA = (
    REPO_ROOT / "sources/ncbi/ncbi_gene2refseq/ncbi-gene2refseq.schema.yaml"
)
GENE2REFSEQ_TRANSFORM = (
    REPO_ROOT / "sources/ncbi/ncbi_gene2refseq/ncbi-gene2refseq.transform.yaml"
)
GENE_GROUP_SCHEMA = REPO_ROOT / "sources/ncbi/ncbi_gene_group/ncbi-gene-group.schema.yaml"
GENE_GROUP_TRANSFORM = (
    REPO_ROOT / "sources/ncbi/ncbi_gene_group/ncbi-gene-group.transform.yaml"
)


def _first_bronze_fixture_path(tmp_path: Path, source: Path = BRONZE) -> Path:
    with source.open("rb") as src:
        line = src.readline()
    fixture = tmp_path / "bronze-one.jsonl"
    fixture.write_bytes(line)
    return fixture

class _FakeDerivation:
    populated_from = None


class _NoIdTransformer:
    def map_object(self, record, source_type, target_type, class_derivation):
        return {}


def test_fragment_without_id_is_rejected():
    outcomes = list(
        transform_bronze_record(
            _NoIdTransformer(),
            record={"gene_id": "1"},
            line_number=1,
            source_row_class="FakeRow",
            class_derivations=[("FakeClass", _FakeDerivation())],
            source_name="fake-source",
        )
    )

    assert len(outcomes) == 1
    assert outcomes[0].accepted is False
    assert outcomes[0].errors == ["Missing id"]
    assert outcomes[0].target_class == "FakeClass"
    assert outcomes[0].line_number == 1

def test_transform_a1bg_envelope(tmp_path):
    bronze_path = _first_bronze_fixture_path(tmp_path)
    outcomes = []
    summary = None
    for outcome in transform_stream(
        source_row_class="NCBIGeneInfoRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="ncbi-gene-info",
    ):
        if isinstance(outcome, TransformSummary):
            summary = outcome
            break
        if outcome.accepted:
            outcomes.append(outcome)

    assert summary is not None
    assert summary.rejected_count == 0

    classes = {o.target_class for o in outcomes}
    assert "GeneAliasRecord" not in classes
    assert "Gene" in classes
    assert "GeneHasDbXref" in classes
    assert "ChromosomeHasGene" in classes

    gene = next(o for o in outcomes if o.target_class == "Gene")
    assert gene.record["id"] == "silkg:Gene:9606:1"
    assert gene.record["tax_id"] == "NCBITaxon:9606"
    assert "HGNC:5" in gene.record["dbxrefs"]
    assert gene.record["same_as"] == gene.record["dbxrefs"]
    assert gene.record["synonyms"][0] == "A1BG"
    assert "A1B" in gene.record["synonyms"]
    assert "alpha-1-B glycoprotein" in gene.record["synonyms"]

    xref_edges = [o for o in outcomes if o.target_class == "GeneHasDbXref"]
    assert len(xref_edges) == 3
    assert all(e.record["predicate"] == "silkg:SAME_AS" for e in xref_edges)

    loc = next(o for o in outcomes if o.target_class == "ChromosomeHasGene")
    assert loc.record["predicate"] == "silkg:HAS_GENE"
    assert loc.record["object"] == "silkg:Gene:9606:1"


def test_no_gene_id_type_collision(tmp_path):
    bronze_path = _first_bronze_fixture_path(tmp_path)
    ids_by_type: dict[tuple[str, str], str] = {}
    for outcome in transform_stream(
        source_row_class="NCBIGeneInfoRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="ncbi-gene-info",
    ):
        if isinstance(outcome, TransformSummary):
            break
        if not outcome.accepted:
            continue
        obj = outcome.record
        key = (obj["id"], obj["@type"])
        assert key not in ids_by_type or ids_by_type[key] == obj["@type"]


def _run_gene2refseq(bronze_path):
    outcomes = []
    for outcome in transform_stream(
        source_row_class="NCBIGene2RefSeqRow",
        bronze_records_path=bronze_path,
        source_schema_path=GENE2REFSEQ_SOURCE_SCHEMA,
        transform_schema_path=GENE2REFSEQ_TRANSFORM,
        source_name="ncbi-gene2refseq",
    ):
        if isinstance(outcome, TransformSummary):
            break
        if outcome.accepted:
            outcomes.append(outcome)
    return outcomes


def test_gene2refseq_models_genomic_sequence_not_gene(tmp_path):
    bronze_path = _first_bronze_fixture_path(tmp_path, GENE2REFSEQ_BRONZE)
    outcomes = _run_gene2refseq(bronze_path)

    classes = {o.target_class for o in outcomes}
    assert "GenomicSequence" in classes
    assert "GenomicSequenceMapsGene" in classes
    # NC/NG/NW accessions are no longer modeled as genes or SAME_AS bridges.
    assert "GeneSameAsGene" not in classes
    assert not any(
        o.target_class == "Gene" and "NC_" in o.record["id"] for o in outcomes
    )

    seq = next(o for o in outcomes if o.target_class == "GenomicSequence")
    assert seq.record["id"] == "silkg:GenomicSequence:9606:NC_000019.10"
    assert seq.record["accession"] == "NC_000019.10"
    assert seq.record["accession_type"] == "chromosome"
    assert seq.record["tax_id"] == "NCBITaxon:9606"

    maps = next(o for o in outcomes if o.target_class == "GenomicSequenceMapsGene")
    assert maps.record["id"] == "silkg:GenomicSequenceMapsGene:9606:NC_000019.10:1"
    assert maps.record["subject"] == "silkg:GenomicSequence:9606:NC_000019.10"
    assert maps.record["object"] == "silkg:Gene:9606:1"
    assert maps.record["predicate"] == "silkg:MAPS_TO"
    assert maps.record["start"] == "58345182"
    assert maps.record["end"] == "58353491"
    assert maps.record["status"] == "REVIEWED"


def test_gene2refseq_maps_gene_edge_ids_unique_per_gene(tmp_path):
    rows = [
        {
            "tax_id": "9606",
            "gene_id": "1",
            "status": "REVIEWED",
            "genomic_nucleotide_accession_version": "NC_000019.10",
            "symbol": "A1BG",
        },
        {
            "tax_id": "9606",
            "gene_id": "2",
            "status": "REVIEWED",
            "genomic_nucleotide_accession_version": "NC_000019.10",
            "symbol": "OTHER",
        },
        {
            "tax_id": "9606",
            "gene_id": "1",
            "status": "REVIEWED",
            "genomic_nucleotide_accession_version": "NC_000019.10",
            "symbol": "A1BG",
        },
    ]
    bronze = tmp_path / "g2r.jsonl"
    bronze.write_bytes(b"".join(dumps_line(r) for r in rows))
    outcomes = _run_gene2refseq(bronze)

    edge_ids = [
        o.record["id"]
        for o in outcomes
        if o.target_class == "GenomicSequenceMapsGene"
    ]
    # Two genes on the same contig get distinct ids; a repeat of the same
    # (contig, gene) reuses the same id (dedup handled downstream).
    assert "silkg:GenomicSequenceMapsGene:9606:NC_000019.10:1" in edge_ids
    assert "silkg:GenomicSequenceMapsGene:9606:NC_000019.10:2" in edge_ids
    assert len(set(edge_ids)) == 2


def test_gene_group_pseudogene_edge(tmp_path):
    row = {
        "tax_id": "9606",
        "gene_id": "1",
        "relationship": "Related pseudogene",
        "other_tax_id": "9606",
        "other_gene_id": "2",
        "subject_uri": "silkg:Gene:9606:1",
        "object_uri": "silkg:Gene:9606:2",
        "edge_class": "GeneHasPseudogene",
        "edge_id": "silkg:GeneHasPseudogene:9606:1:2",
        "edge_predicate": "silkg:PSEUDOGENE",
    }
    bronze = tmp_path / "gene-group.jsonl"
    bronze.write_bytes(dumps_line(row))
    outcomes = []
    for outcome in transform_stream(
        source_row_class="NCBIGeneGroupRow",
        bronze_records_path=bronze,
        source_schema_path=GENE_GROUP_SCHEMA,
        transform_schema_path=GENE_GROUP_TRANSFORM,
        source_name="ncbi-gene-group",
    ):
        if isinstance(outcome, TransformSummary):
            break
        if outcome.accepted:
            outcomes.append(outcome)

    classes = {o.target_class for o in outcomes}
    assert classes == {"Gene", "GeneHasPseudogene"}
    edge = next(o for o in outcomes if o.target_class == "GeneHasPseudogene")
    assert edge.record["id"] == "silkg:GeneHasPseudogene:9606:1:2"
    assert edge.record["subject"] == "silkg:Gene:9606:1"
    assert edge.record["object"] == "silkg:Gene:9606:2"
    assert edge.record["predicate"] == "silkg:PSEUDOGENE"


def test_workers_two_matches_workers_one(tmp_path):
    from pipeline.transform.runner import _write_stream_shard

    bronze_path = BRONZE
    single_frag = tmp_path / "fragments.one.jsonl"
    single_q = tmp_path / "quarantine.one.jsonl"
    run_id = "workers-cmp"
    summary = _write_stream_shard(
        source_row_class="NCBIGeneInfoRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="ncbi-gene-info",
        run_id=run_id,
        fragments_path=single_frag,
        quarantine_path=single_q,
    )
    assert summary.rejected_count == 0
    one = single_frag.read_bytes()

    total_lines = sum(1 for _ in bronze_path.open("rb"))
    ranges = _line_ranges(total_lines, 2)
    frag_parts = []
    q_parts = []
    for i, (start, end) in enumerate(ranges):
        frag_part = tmp_path / f"fragments.part{i}.jsonl"
        q_part = tmp_path / f"quarantine.part{i}.jsonl"
        frag_parts.append(frag_part)
        q_parts.append(q_part)
        result = _worker_shard(
            {
                "part_index": i,
                "start": start,
                "end": end,
                "source_row_class": "NCBIGeneInfoRow",
                "bronze_records_path": str(bronze_path),
                "source_schema_path": str(SOURCE_SCHEMA),
                "transform_schema_path": str(TRANSFORM),
                "source_name": "ncbi-gene-info",
                "run_id": run_id,
                "fragments_path": str(frag_part),
                "quarantine_path": str(q_part),
            }
        )
        assert result["rejected_count"] == 0

    merged = tmp_path / "fragments.two.jsonl"
    _concat_parts(frag_parts, merged)
    assert merged.read_bytes() == one


def test_limit_caps_bronze_rows(tmp_path):
    bronze_path = BRONZE
    outcomes = []
    summary = None
    for outcome in transform_stream(
        source_row_class="NCBIGeneInfoRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="ncbi-gene-info",
        limit=2,
    ):
        if isinstance(outcome, TransformSummary):
            summary = outcome
            break
        outcomes.append(outcome)
    assert summary is not None
    assert summary.input_record_count == 2


def test_parse_ncbi_feature_types():
    assert parse_ncbi_feature_types(None) is None
    assert parse_ncbi_feature_types("") is None
    assert parse_ncbi_feature_types(
        "regulatory:enhancer|regulatory:silencer"
    ) == ["enhancer", "silencer"]
    assert parse_ncbi_feature_types(
        "regulatory:DNase_I_hypersensitive_site|misc_recomb:meiotic"
    ) == ["DNase_I_hypersensitive_site", "meiotic"]


def test_transform_parses_feature_types(tmp_path):
    bronze_path = tmp_path / "bronze-region.jsonl"
    bronze_path.write_bytes(
        dumps_line(
            {
                "tax_id": "9606",
                "gene_id": "106560211",
                "symbol": "LOC106560211",
                "synonyms": [],
                "dbxrefs": [],
                "chromosome": "2",
                "map_location": "2p",
                "description": "APOB 5' regulatory region",
                "type_of_gene": "biological-region",
                "symbol_from_nomenclature_authority": None,
                "full_name_from_nomenclature_authority": None,
                "nomenclature_status": None,
                "other_designations": [],
                "modification_date": "20260519",
                "feature_type": (
                    "regulatory:DNase_I_hypersensitive_site|"
                    "regulatory:enhancer|regulatory:silencer"
                ),
                "all_synonyms": ["LOC106560211"],
            }
        )
    )

    gene = None
    for outcome in transform_stream(
        source_row_class="NCBIGeneInfoRow",
        bronze_records_path=bronze_path,
        source_schema_path=SOURCE_SCHEMA,
        transform_schema_path=TRANSFORM,
        source_name="ncbi-gene-info",
    ):
        if isinstance(outcome, TransformSummary):
            break
        if outcome.accepted and outcome.target_class == "Gene":
            gene = outcome.record

    assert gene is not None
    assert "feature_type" not in gene
    assert gene["feature_types"] == [
        "DNase_I_hypersensitive_site",
        "enhancer",
        "silencer",
    ]
