from pipeline.integrate.merge import (
    _dedup_key,
    apply_edge_contribution,
    apply_node_contribution,
    finalize_node,
    merge_edge_fragments,
    merge_node_fragments,
)
from pipeline.integrate.priorities import IntegratePriorities


def test_dedup_key_dicts_and_scalars():
    assert _dedup_key("A1BG") == "A1BG"
    assert _dedup_key({"b": 1, "a": 2}) == (("a", "2"), ("b", "1"))
    assert _dedup_key([{"x": 1}, "y"]) == ((("x", "1"),), "y")


def test_multivalued_dedup_union():
    priorities = IntegratePriorities(source_ranks={"ncbi-gene-info": 100}, slot_overrides={})
    contributions = [
        (
            "ncbi-gene-info",
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "synonyms": ["A1BG", "A1B"],
            },
            {"source_name": "ncbi-gene-info", "silver_run_id": "r1", "bronze_line": 0},
        ),
        (
            "ncbi-gene-info",
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "synonyms": ["A1B", "GAB"],
            },
            {"source_name": "ncbi-gene-info", "silver_run_id": "r1", "bronze_line": 1},
        ),
    ]
    merged = merge_node_fragments(("silkg:Gene:9606:1", "Gene"), contributions, priorities)
    assert merged["synonyms"] == ["A1BG", "A1B", "GAB"]


def test_priority_merge_uses_higher_rank_source():
    priorities = IntegratePriorities(
        source_ranks={"ncbi-gene-info": 100, "ncbi-gene-summary": 90},
        slot_overrides={
            "Gene": {
                "description": ["ncbi-gene-summary", "ncbi-gene-info"],
            }
        },
    )
    contributions = [
        (
            "ncbi-gene-info",
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "symbol": "A1BG",
                "description": "from gene-info",
            },
            {"source_name": "ncbi-gene-info", "silver_run_id": "r1", "bronze_line": 0},
        ),
        (
            "ncbi-gene-summary",
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "description": "from gene-summary",
            },
            {"source_name": "ncbi-gene-summary", "silver_run_id": "r1", "bronze_line": 0},
        ),
    ]
    merged = merge_node_fragments(("silkg:Gene:9606:1", "Gene"), contributions, priorities)
    assert merged["description"] == "from gene-summary"
    assert merged["symbol"] == "A1BG"
    assert len(merged["sources"]) == 2
    assert any(a["slot"] == "description" for a in merged.get("alternates", []))


def test_fold_matches_batch_node_merge():
    priorities = IntegratePriorities(
        source_ranks={"ncbi-gene-info": 100, "ncbi-gene-summary": 90},
        slot_overrides={
            "Gene": {
                "description": ["ncbi-gene-summary", "ncbi-gene-info"],
            }
        },
    )
    contributions = [
        (
            "ncbi-gene-info",
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "symbol": "A1BG",
                "description": "from gene-info",
                "synonyms": ["A1BG", "A1B"],
            },
            {"source_name": "ncbi-gene-info", "silver_run_id": "r1", "bronze_line": 0},
        ),
        (
            "ncbi-gene-summary",
            {
                "id": "silkg:Gene:9606:1",
                "@type": "Gene",
                "description": "from gene-summary",
                "synonyms": ["A1B", "GAB"],
            },
            {"source_name": "ncbi-gene-summary", "silver_run_id": "r1", "bronze_line": 1},
        ),
    ]
    node_key = ("silkg:Gene:9606:1", "Gene")
    batch = merge_node_fragments(node_key, contributions, priorities)

    state = None
    for contribution in contributions:
        state = apply_node_contribution(state, node_key, contribution, priorities)
    folded = finalize_node(state)

    assert folded == batch


def test_fold_matches_batch_edge_merge():
    contributions = [
        (
            "tflink-tf-interactions",
            {
                "@type": "TFInteractsWithGene",
                "subject": "silkg:Protein:9606:1",
                "object": "silkg:Gene:9606:2",
            },
            {"source_name": "tflink-tf-interactions", "silver_run_id": "r1", "bronze_line": 0},
        ),
        (
            "tflink-tf-interactions",
            {
                "@type": "TFInteractsWithGene",
                "subject": "silkg:Protein:9606:1",
                "object": "silkg:Gene:9606:2",
            },
            {"source_name": "tflink-tf-interactions", "silver_run_id": "r1", "bronze_line": 1},
        ),
    ]
    batch = merge_edge_fragments(contributions)

    merged = None
    for contribution in contributions:
        merged = apply_edge_contribution(merged, contribution)

    assert merged == batch
