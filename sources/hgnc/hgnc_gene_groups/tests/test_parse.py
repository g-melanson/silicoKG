from __future__ import annotations

from pathlib import Path

import pytest

from sources.hgnc.hgnc_gene_groups.parse import (
    build_hgnc_to_entrez_index,
    iter_gene_group_rows,
    iter_hierarchy_rows,
    iter_hgnc_gene_group_rows,
    iter_membership_rows,
    load_hgnc_json,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_hgnc_json_strips_text_header(tmp_path: Path) -> None:
    payload_path = tmp_path / "complete_set.json"
    payload_path.write_text(
        "Source URL: example\nTitle: test\n\n"
        '{"response":{"docs":[{"hgnc_id":"HGNC:1","entrez_id":"1"}]}}',
        encoding="utf-8",
    )
    payload = load_hgnc_json(payload_path)
    assert payload["response"]["docs"][0]["hgnc_id"] == "HGNC:1"


def test_build_hgnc_to_entrez_index() -> None:
    index = build_hgnc_to_entrez_index(FIXTURES / "hgnc_complete_set.json")
    assert index["5"] == "1"


def test_iter_gene_group_rows_group_594() -> None:
    rows = list(iter_gene_group_rows(FIXTURES / "family.csv"))
    group_594 = next(row for row in rows if row["family_id"] == "594")
    assert group_594["label"] == "Immunoglobulin like domain containing"
    assert group_594["definition"] is None

    group_589 = next(row for row in rows if row["family_id"] == "589")
    assert group_589["definition"] == "Superfamily definition."


def test_iter_hierarchy_rows_594_subclass_of_589() -> None:
    rows = list(iter_hierarchy_rows(FIXTURES / "hierarchy.csv"))
    assert rows == [
        {
            "row_kind": "hierarchy_edge",
            "parent_fam_id": "589",
            "child_fam_id": "594",
        }
    ]


def test_iter_membership_rows_a1bg_in_group_594() -> None:
    index = build_hgnc_to_entrez_index(FIXTURES / "hgnc_complete_set.json")
    rows = list(iter_membership_rows(FIXTURES / "gene_has_family.csv", index))
    assert rows == [
        {
            "row_kind": "membership_edge",
            "hgnc_id": "5",
            "family_id": "594",
            "entrez_id": "1",
        }
    ]


def test_iter_hgnc_gene_group_rows_with_local_companions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_resolve(**kwargs):  # noqa: ANN003
        return {
            "hierarchy": FIXTURES / "hierarchy.csv",
            "gene_has_family": FIXTURES / "gene_has_family.csv",
            "complete_set": FIXTURES / "hgnc_complete_set.json",
        }

    monkeypatch.setattr(
        "sources.hgnc.hgnc_gene_groups.parse.resolve_companion_paths",
        fake_resolve,
    )

    rows = list(iter_hgnc_gene_group_rows(FIXTURES / "family.csv"))
    kinds = {row["row_kind"] for row in rows}
    assert kinds == {"gene_group", "hierarchy_edge", "membership_edge"}

    membership = next(row for row in rows if row["row_kind"] == "membership_edge")
    assert membership["entrez_id"] == "1"
    assert membership["family_id"] == "594"
