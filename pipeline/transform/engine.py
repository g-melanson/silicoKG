from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml
from linkml_map import ObjectTransformer
from linkml_map.datamodel.transformer_model import TransformationSpecification
from linkml_map.transformer.transformer import Transformer
from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.utils.schemaview import SchemaView

from pipeline.identity.constants import EDGE_CLASS_TO_PREDICATE
from pipeline.identity.dbxrefs import normalize_dbxrefs
from pipeline.identity.uris import gene_has_dbxref_id, gene_uri
from pipeline.io.jsonl import loads_line
from pipeline.ontology.go_uri import (
    go_predicate_label,
    go_term_node_id,
    load_go_aspect_map,
)
from pipeline.progress import iter_file_lines, track
from pipeline.validate.engine import load_validation_schema

CANONICAL_GENE_ENRICHMENT_SOURCES = frozenset({"ncbi-gene-info"})


@dataclass
class TransformOutcome:
    line_number: int
    target_class: str
    record: dict
    bronze_record: dict
    errors: list[str]
    accepted: bool


@dataclass
class TransformSummary:
    input_record_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


def source_schemaview(source_schema_path: Path) -> SchemaView:
    return SchemaView(yaml_dumper.dumps(load_validation_schema(source_schema_path)))


def load_transform_spec(transform_schema_path: Path) -> TransformationSpecification:
    with transform_schema_path.open(encoding="utf-8") as f:
        spec_dict = yaml.safe_load(f)
    Transformer._normalize_spec_dict(spec_dict)
    return TransformationSpecification(**spec_dict)


def parse_ncbi_feature_types(raw: str | None) -> list[str] | None:
    """Parse NCBI Feature_type pipe-delimited category:token values to token list."""
    if not raw:
        return None
    return [part.split(":", 1)[-1] for part in raw.split("|")]


def _enrich_gene_fragment(fragment: dict, bronze_record: dict) -> tuple[dict, list[str]]:
    tax_id = str(bronze_record["tax_id"])
    gene_id = str(bronze_record["gene_id"])
    dbxrefs, xref_errors = normalize_dbxrefs(bronze_record.get("dbxrefs"))
    fragment = dict(fragment)
    fragment["id"] = gene_uri(tax_id, gene_id)
    fragment["tax_id"] = f"NCBITaxon:{tax_id}"
    if dbxrefs:
        fragment["dbxrefs"] = dbxrefs
        fragment["same_as"] = list(dbxrefs)
    feature_types = parse_ncbi_feature_types(bronze_record.get("feature_type"))
    if feature_types:
        fragment["feature_types"] = feature_types
    return fragment, xref_errors


def _build_gene_has_dbxref_fragments(
    bronze_record: dict,
    normalized_xrefs: list[str],
) -> list[dict]:
    if not normalized_xrefs:
        return []
    tax_id = str(bronze_record["tax_id"])
    gene_id = str(bronze_record["gene_id"])
    subject = gene_uri(tax_id, gene_id)
    fragments: list[dict] = []
    for xref in normalized_xrefs:
        fragments.append(
            {
                "id": gene_has_dbxref_id(tax_id, gene_id, xref),
                "subject": subject,
                "predicate": EDGE_CLASS_TO_PREDICATE["GeneHasDbXref"],
                "object": xref,
                "@type": "GeneHasDbXref",
            }
        )
    return fragments


SKIP_WITHOUT_REQUIRED_FIELD: dict[str, str] = {
    "Chromosome": "chromosome",
    "ChromosomeHasGene": "chromosome",
    "GeneHasProductTranscript": "rna_nucleotide_accession_version",
    "TranscriptHasProductProtein": "protein_accession_version",
    "ProteinHasProductMaturePeptide": "mature_peptide_accession_version",
    "ProteinHasMaturePeptideProduct": "mature_peptide_accession_version",
    "GeneSameAsGene": "genomic_nucleotide_accession_version",
    "GeneVariant": "genomic_nucleotide_gi",
    "GeneHasGeneVariant": "genomic_nucleotide_gi",
    "TranscriptVariant": "rna_nucleotide_gi",
    "TranscriptHasTranscriptVariant": "rna_nucleotide_gi",
    "ProteinVariant": "protein_gi",
    "ProteinHasProteinVariant": "protein_gi",
    "MaturePeptideVariant": "mature_peptide_gi",
    "ProteinHasMaturePeptideVariant": "mature_peptide_gi",
}

SOURCE_SKIP_WITHOUT_REQUIRED_FIELD: dict[str, dict[str, str]] = {
    "ncbi-gene2refseq": {
        "GenomicSequence": "genomic_nucleotide_accession_version",
        "GenomicSequenceMapsGene": "genomic_nucleotide_accession_version",
    },
    "obo-go": {
        "GOIsA": "predicate_id",
        "GOObjectPropertyEdge": "predicate_id",
    },
}


def _required_field(source_name: str, target_class: str) -> str | None:
    source_skip = SOURCE_SKIP_WITHOUT_REQUIRED_FIELD.get(source_name, {})
    if target_class in source_skip:
        return source_skip[target_class]
    return SKIP_WITHOUT_REQUIRED_FIELD.get(target_class)


def transform_bronze_record(
    transformer,
    record,
    line_number,
    source_row_class,
    class_derivations,
    source_name: str,
):
    normalized_xrefs: list[str] = []

    for target_class, class_derivation in class_derivations:
        required_field = _required_field(source_name, target_class)
        if required_field and not record.get(required_field):
            continue
        try:
            source_type = class_derivation.populated_from or source_row_class
            fragment = transformer.map_object(
                record,
                source_type=source_type,
                target_type=target_class,
                class_derivation=class_derivation,
            )
            fragment["@type"] = target_class

            if not fragment.get("id"):
                continue

            if target_class == "GOObjectPropertyEdge" and (
                not fragment.get("subject") or not fragment.get("object")
            ):
                continue

            if target_class == "Gene" and source_name in CANONICAL_GENE_ENRICHMENT_SOURCES:
                fragment, _xref_errors = _enrich_gene_fragment(fragment, record)
                normalized_xrefs = fragment.get("dbxrefs", [])

            yield TransformOutcome(
                line_number=line_number,
                target_class=target_class,
                record=fragment,
                bronze_record=record,
                errors=[],
                accepted=True,
            )
        except Exception as e:
            yield TransformOutcome(
                line_number=line_number,
                target_class=target_class,
                record=record,
                bronze_record=record,
                errors=[str(e)],
                accepted=False,
            )

    for xref_fragment in _build_gene_has_dbxref_fragments(record, normalized_xrefs):
        yield TransformOutcome(
            line_number=line_number,
            target_class="GeneHasDbXref",
            record=xref_fragment,
            bronze_record=record,
            errors=[],
            accepted=True,
        )


def transform_stream(
    source_row_class: str,
    bronze_records_path: Path,
    source_schema_path: Path,
    transform_schema_path: Path,
    source_name: str,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
):
    summary = TransformSummary()
    transformer = build_object_transformer(
        source_schema_path,
        transform_schema_path,
        source_name=source_name,
        bronze_records_path=bronze_records_path,
    )
    class_derivations = [
        (cd.name, cd) for cd in transformer.specification.class_derivations
    ]

    for line_number, record in iter_bronze_records(
        bronze_records_path,
        start=start,
        end=end,
        limit=limit,
    ):
        summary.input_record_count += 1
        for outcome in transform_bronze_record(
            transformer,
            record,
            line_number,
            source_row_class,
            class_derivations,
            source_name,
        ):
            if outcome.accepted:
                summary.accepted_count += 1
            else:
                summary.rejected_count += 1
                for error in outcome.errors:
                    summary.error_counts[error] = summary.error_counts.get(error, 0) + 1
            yield outcome
    yield summary


def build_object_transformer(
    source_schema_path: Path,
    transform_schema_path: Path,
    *,
    source_name: str | None = None,
    bronze_records_path: Path | None = None,
) -> ObjectTransformer:
    transformer = ObjectTransformer()
    transformer.source_schemaview = source_schemaview(source_schema_path)
    transformer.specification = load_transform_spec(transform_schema_path)
    if source_name == "obo-go":
        aspect_map = (
            load_go_aspect_map(bronze_records_path)
            if bronze_records_path is not None
            else {}
        )
        transformer.extension_functions = {
            "go_term_uri": lambda term_id, aspect=None: go_term_node_id(
                term_id, aspect, aspect_map
            ),
            "go_predicate_label": go_predicate_label,
        }
    return transformer


def iter_bronze_records(
    file_path: Path,
    *,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
) -> Iterator[tuple[int, dict]]:
    """Yield `(line_number, record)` for bronze JSONL.

    ``start``/``end`` are half-open line indexes ``[start, end)``.
    ``limit`` caps how many records are yielded after ``start``.
    """
    yielded = 0
    sharded = start > 0 or end is not None
    if sharded:
        with file_path.open("rb") as handle:
            line_iter = enumerate(handle)
            for line_number, line in line_iter:
                if line_number < start:
                    continue
                if end is not None and line_number >= end:
                    break
                if not line.strip():
                    continue
                yield line_number, loads_line(line)
                yielded += 1
                if limit is not None and yielded >= limit:
                    break
        return

    for line_number, line in enumerate(
        iter_file_lines(
            file_path,
            desc=f"transform {file_path.parent.name}",
        )
    ):
        if line_number < start:
            continue
        if end is not None and line_number >= end:
            break
        if not line.strip():
            continue
        yield line_number, loads_line(line)
        yielded += 1
        if limit is not None and yielded >= limit:
            break


def count_bronze_lines(file_path: Path) -> int:
    from pipeline.progress import count_lines

    return count_lines(file_path)


def transform_records(
    records_path: Path,
    transform_schema_path: Path,
    source_schema_path: Path,
    source_row_class: str,
    source_name: str,
) -> tuple[TransformSummary, list[TransformOutcome]]:
    summary = TransformSummary()
    outcomes: list[TransformOutcome] = []
    for outcome in transform_stream(
        source_row_class=source_row_class,
        bronze_records_path=records_path,
        source_schema_path=source_schema_path,
        transform_schema_path=transform_schema_path,
        source_name=source_name,
    ):
        if isinstance(outcome, TransformSummary):
            summary = outcome
            break
        outcomes.append(outcome)
    return summary, outcomes
