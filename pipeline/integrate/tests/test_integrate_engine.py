from __future__ import annotations

import json
from pathlib import Path

from pipeline.identity.fragments import build_fragment_envelope
from pipeline.integrate.engine import integrate_silver_paths
from pipeline.integrate.priorities import load_priorities

REPO = Path(__file__).resolve().parents[3]


def test_integrate_single_gene_fragment(tmp_path):
    fragment = build_fragment_envelope(
        target_class="Gene",
        obj={
            "id": "silkg:Gene:9606:1",
            "@type": "Gene",
            "symbol": "A1BG",
        },
        source_name="ncbi-gene-info",
        silver_run_id="test-run",
        bronze_line=0,
        bronze_record={"gene_id": "1", "tax_id": "9606"},
    )
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(json.dumps(fragment) + "\n", encoding="utf-8")

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 0
    assert len(nodes) == 1
    assert nodes[0]["id"] == "silkg:Gene:9606:1"
    assert nodes[0]["sources"][0]["source_name"] == "ncbi-gene-info"
    assert edges == []


def test_integrate_reified_edge_becomes_relationship_not_node(tmp_path):
    fragment = build_fragment_envelope(
        target_class="GeneHasPseudogene",
        obj={
            "id": "silkg:GeneHasPseudogene:9606:1:2",
            "@type": "GeneHasPseudogene",
            "subject": "silkg:Gene:9606:1",
            "predicate": "silkg:PSEUDOGENE",
            "object": "silkg:Pseudogene:9606:2",
        },
        source_name="ncbi-gene-group",
        silver_run_id="test-run",
        bronze_line=0,
        bronze_record={"gene_id": "1", "tax_id": "9606"},
    )
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(json.dumps(fragment) + "\n", encoding="utf-8")

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 0
    assert nodes == []
    assert len(edges) == 1
    assert edges[0]["@type"] == "GeneHasPseudogene"
    assert edges[0]["subject"] == "silkg:Gene:9606:1"
    assert edges[0]["object"] == "silkg:Pseudogene:9606:2"
    assert edges[0]["predicate"] == "silkg:PSEUDOGENE"


def test_integrate_genomic_sequence_is_node(tmp_path):
    fragment = build_fragment_envelope(
        target_class="GenomicSequence",
        obj={
            "id": "silkg:GenomicSequence:9606:NC_000019.10",
            "@type": "GenomicSequence",
            "accession": "NC_000019.10",
            "accession_type": "chromosome",
            "tax_id": "NCBITaxon:9606",
        },
        source_name="ncbi-gene2refseq",
        silver_run_id="test-run",
        bronze_line=0,
        bronze_record={"gene_id": "1", "tax_id": "9606"},
    )
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(json.dumps(fragment) + "\n", encoding="utf-8")

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 0
    assert edges == []
    assert len(nodes) == 1
    assert nodes[0]["id"] == "silkg:GenomicSequence:9606:NC_000019.10"
    assert nodes[0]["@type"] == "GenomicSequence"


def test_integrate_genomic_sequence_maps_gene_is_edge(tmp_path):
    fragment = build_fragment_envelope(
        target_class="GenomicSequenceMapsGene",
        obj={
            "id": "silkg:GenomicSequenceMapsGene:9606:NC_000019.10:1",
            "@type": "GenomicSequenceMapsGene",
            "subject": "silkg:GenomicSequence:9606:NC_000019.10",
            "predicate": "silkg:MAPS_TO",
            "object": "silkg:Gene:9606:1",
            "start": "58345182",
            "end": "58353491",
        },
        source_name="ncbi-gene2refseq",
        silver_run_id="test-run",
        bronze_line=0,
        bronze_record={"gene_id": "1", "tax_id": "9606"},
    )
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(json.dumps(fragment) + "\n", encoding="utf-8")

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 0
    assert nodes == []
    assert len(edges) == 1
    assert edges[0]["@type"] == "GenomicSequenceMapsGene"
    assert edges[0]["predicate"] == "silkg:MAPS_TO"
    assert edges[0]["object"] == "silkg:Gene:9606:1"


def test_integrate_quarantines_edge_with_missing_object(tmp_path):
    fragment = build_fragment_envelope(
        target_class="ProteinHasProductMaturePeptide",
        obj={
            "id": "silkg:ProteinHasProductMaturePeptide:9606:1:NP_570602.2",
            "@type": "ProteinHasProductMaturePeptide",
            "subject": "silkg:Protein:9606:1:NP_570602.2",
            "predicate": "silkg:HAS_PROTEIN_PRODUCT",
            "object": None,
        },
        source_name="ncbi-gene2refseq",
        silver_run_id="test-run",
        bronze_line=0,
        bronze_record={"gene_id": "1", "tax_id": "9606"},
    )
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(json.dumps(fragment) + "\n", encoding="utf-8")

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 1
    assert nodes == []
    assert edges == []
    assert quarantine[0]["errors"] == ["edge missing object"]


def _maps_gene_fragment(
    *,
    subject: str,
    start: str,
    end: str,
    bronze_line: int,
    status: str = "REVIEWED",
) -> dict:
    gene_id = "1"
    accession = subject.rsplit(":", 1)[-1]
    return build_fragment_envelope(
        target_class="GenomicSequenceMapsGene",
        obj={
            "id": f"silkg:GenomicSequenceMapsGene:9606:{accession}:{gene_id}",
            "@type": "GenomicSequenceMapsGene",
            "subject": subject,
            "predicate": "silkg:MAPS_TO",
            "object": "silkg:Gene:9606:1",
            "start": start,
            "end": end,
            "status": status,
        },
        source_name="ncbi-gene2refseq",
        silver_run_id="test-run",
        bronze_line=bronze_line,
        bronze_record={"gene_id": gene_id, "tax_id": "9606"},
    )


def test_integrate_different_subject_yields_two_edges(tmp_path):
    fragments = [
        _maps_gene_fragment(
            subject="silkg:GenomicSequence:9606:NC_000019.10",
            start="100",
            end="200",
            bronze_line=0,
        ),
        _maps_gene_fragment(
            subject="silkg:GenomicSequence:9606:NC_060943.1",
            start="100",
            end="200",
            bronze_line=1,
        ),
    ]
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(
        "".join(json.dumps(f) + "\n" for f in fragments), encoding="utf-8"
    )

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 0
    assert nodes == []
    assert len(edges) == 2
    subjects = {edge["subject"] for edge in edges}
    assert subjects == {
        "silkg:GenomicSequence:9606:NC_000019.10",
        "silkg:GenomicSequence:9606:NC_060943.1",
    }
    assert summary.edge_payload_conflicts == 0


def test_integrate_counts_edge_payload_conflicts(tmp_path):
    fragments = [
        _maps_gene_fragment(
            subject="silkg:GenomicSequence:9606:NC_000019.10",
            start="100",
            end="200",
            bronze_line=0,
            status="REVIEWED",
        ),
        _maps_gene_fragment(
            subject="silkg:GenomicSequence:9606:NC_000019.10",
            start="999",
            end="888",
            bronze_line=1,
            status="MODEL",
        ),
    ]
    silver = tmp_path / "fragments.jsonl"
    silver.write_text(
        "".join(json.dumps(f) + "\n" for f in fragments), encoding="utf-8"
    )

    nodes, edges, quarantine, summary = integrate_silver_paths(
        [silver], load_priorities(REPO / "schemas" / "integrate-priorities.yaml")
    )
    assert summary.quarantine_count == 0
    assert len(edges) == 1
    assert edges[0]["start"] == "100"
    assert edges[0]["end"] == "200"
    assert edges[0]["status"] == "REVIEWED"
    assert len(edges[0]["sources"]) == 2
    assert summary.edge_payload_conflicts == 3
    sample_slots = {s["slot"] for s in summary.edge_payload_conflict_samples}
    assert sample_slots == {"start", "end", "status"}
    assert edges[0].get("alternates") is None
