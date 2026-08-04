"""Parse HGNC gene group CSV tables and complete-set JSON crosswalk."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from pipeline.ingest.fetch import ensure_cached_download
from pipeline.paths import DEFAULT_PATHS

GCS_BASE = "https://storage.googleapis.com/public-download-files/hgnc"
FAMILY_URL = f"{GCS_BASE}/csv/csv/genefamily_db_tables/family.csv"
HIERARCHY_URL = f"{GCS_BASE}/csv/csv/genefamily_db_tables/hierarchy.csv"
GENE_HAS_FAMILY_URL = f"{GCS_BASE}/csv/csv/genefamily_db_tables/gene_has_family.csv"
COMPLETE_SET_URL = f"{GCS_BASE}/json/json/hgnc_complete_set.json"

SOURCE_NAME = "hgnc-gene-groups"
DEFAULT_TTL_SECONDS = 21600
_NULL_VALUES = frozenset({"", "NULL", "null"})


def _nullify(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped in _NULL_VALUES:
        return None
    return stripped


def _normalize_hgnc_id(value: str | None) -> str | None:
    normalized = _nullify(value)
    if normalized is None:
        return None
    if normalized.upper().startswith("HGNC:"):
        return normalized.split(":", 1)[1]
    return normalized


def load_hgnc_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    start = text.find("{")
    if start < 0:
        raise ValueError(f"no JSON object found in {path}")
    return json.loads(text[start:])


def build_hgnc_to_entrez_index(complete_set_path: Path) -> dict[str, str]:
    payload = load_hgnc_json(complete_set_path)
    docs = payload.get("response", {}).get("docs", [])
    index: dict[str, str] = {}
    for doc in docs:
        hgnc_id = _normalize_hgnc_id(doc.get("hgnc_id"))
        entrez_id = _nullify(str(doc.get("entrez_id")) if doc.get("entrez_id") is not None else None)
        if hgnc_id and entrez_id:
            index[hgnc_id] = entrez_id
    return index


def _read_csv(path: Path) -> Iterator[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {key: (value if value is not None else "") for key, value in row.items()}


def iter_gene_group_rows(family_path: Path) -> Iterator[dict]:
    for row in _read_csv(family_path):
        family_id = _nullify(row.get("id"))
        label = _nullify(row.get("name"))
        if not family_id or not label:
            continue
        yield {
            "row_kind": "gene_group",
            "family_id": family_id,
            "label": label,
            "definition": _nullify(row.get("desc_comment")),
        }


def iter_hierarchy_rows(hierarchy_path: Path) -> Iterator[dict]:
    for row in _read_csv(hierarchy_path):
        parent_fam_id = _nullify(row.get("parent_fam_id"))
        child_fam_id = _nullify(row.get("child_fam_id"))
        if not parent_fam_id or not child_fam_id:
            continue
        yield {
            "row_kind": "hierarchy_edge",
            "parent_fam_id": parent_fam_id,
            "child_fam_id": child_fam_id,
        }


def iter_membership_rows(
    gene_has_family_path: Path,
    hgnc_to_entrez: dict[str, str],
) -> Iterator[dict]:
    for row in _read_csv(gene_has_family_path):
        hgnc_id = _normalize_hgnc_id(row.get("hgnc_id"))
        family_id = _nullify(row.get("family_id"))
        if not hgnc_id or not family_id:
            continue
        entrez_id = hgnc_to_entrez.get(hgnc_id)
        if not entrez_id:
            continue
        yield {
            "row_kind": "membership_edge",
            "hgnc_id": hgnc_id,
            "family_id": family_id,
            "entrez_id": entrez_id,
        }


def resolve_companion_paths(
    *,
    cache_dir: Path | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Path]:
    cache = cache_dir or DEFAULT_PATHS.source_cache_dir(SOURCE_NAME)
    return {
        "hierarchy": ensure_cached_download(
            HIERARCHY_URL,
            cache,
            "hierarchy.csv",
            ttl_seconds=ttl_seconds,
        ),
        "gene_has_family": ensure_cached_download(
            GENE_HAS_FAMILY_URL,
            cache,
            "gene_has_family.csv",
            ttl_seconds=ttl_seconds,
        ),
        "complete_set": ensure_cached_download(
            COMPLETE_SET_URL,
            cache,
            "hgnc_complete_set.json",
            ttl_seconds=ttl_seconds,
        ),
    }


def iter_hgnc_gene_group_rows(
    family_path: Path,
    *,
    cache_dir: Path | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Iterator[dict]:
    companions = resolve_companion_paths(cache_dir=cache_dir, ttl_seconds=ttl_seconds)
    hgnc_to_entrez = build_hgnc_to_entrez_index(companions["complete_set"])

    yield from iter_gene_group_rows(family_path)
    yield from iter_hierarchy_rows(companions["hierarchy"])
    yield from iter_membership_rows(companions["gene_has_family"], hgnc_to_entrez)
