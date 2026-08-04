from __future__ import annotations

import json
from pathlib import Path

from pipeline.ontology.classify.engine import classify_merged_paths

FIXTURES = Path(__file__).parent / "fixtures"


def test_missing_endpoint_emits_quarantine_stub(tmp_path):
    nodes_path = tmp_path / "nodes.jsonl"
    edges_path = tmp_path / "edges.jsonl"
    index_path = FIXTURES / "minimal-index.yaml"
    rules_path = FIXTURES / "classification-rules.yaml"

    nodes_path.write_text(
        json.dumps(
            {
                "id": "silkg:Gene:9606:100",
                "@type": "Gene",
                "symbol": "CHILD",
                "tax_id": "NCBITaxon:9606",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    edges_path.write_text(
        json.dumps(
            {
                "id": "silkg:GeneHasReadthroughParent:9606:100:999",
                "@type": "GeneHasReadthroughParent",
                "subject": "silkg:Gene:9606:100",
                "predicate": "silkg:READTHROUGH_PARENT",
                "object": "silkg:Gene:9606:999",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    nodes, quarantine, summary = classify_merged_paths(
        nodes_path,
        edges_path,
        index_path=index_path,
        rules_path=rules_path,
    )

    assert len(nodes) == 1
    assert "so_types" not in nodes[0]
    assert quarantine == [{"id": "silkg:Gene:9606:999", "@type": "Gene"}]
    assert summary.quarantined_stub_count == 1
    assert summary.quarantined_missing_endpoints == [
        {
            "id": "silkg:Gene:9606:999",
            "@type": "Gene",
            "rule_id": "readthrough-parent-is-fusion-gene",
        }
    ]
