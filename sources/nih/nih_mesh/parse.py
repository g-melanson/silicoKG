from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import yaml

PREDICATE_ID = "mesh:broaderDescriptor"
_ALLOWLIST_PATH = Path(__file__).with_name("allowlist.yaml")


def load_allowlist(path: Path = _ALLOWLIST_PATH) -> list[str]:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return list(config.get("roots") or []) + list(config.get("leaf") or [])


def _text(elem: ET.Element, path: str) -> str | None:
    child = elem.find(path)
    if child is None or not child.text:
        return None
    return child.text.strip()


def parent_tree(tree: str) -> str | None:
    if "." not in tree:
        return None
    return tree.rsplit(".", 1)[0]


def matches_allowlist(tree_numbers: list[str], prefixes: list[str]) -> bool:
    return any(
        tree == prefix or tree.startswith(prefix + ".")
        for tree in tree_numbers
        for prefix in prefixes
    )


def parse_descriptor_record(elem: ET.Element) -> dict:
    preferred = next(
        (c for c in elem.findall(".//Concept") if c.get("PreferredConceptYN") == "Y"),
        None,
    )

    synonyms: list[str] = []
    if preferred is not None:
        for term in preferred.findall(".//Term"):
            if term.get("IsPermutedTermYN") == "Y":
                continue
            label = _text(term, "String")
            if label:
                synonyms.append(label)

    return {
        "descriptor_ui": _text(elem, "DescriptorUI"),
        "label": _text(elem, "DescriptorName/String"),
        "tree_numbers": [
            tree_number.text.strip()
            for tree_number in elem.findall(".//TreeNumber")
            if tree_number.text
        ],
        "scope_note": _text(preferred, "ScopeNote") if preferred is not None else None,
        "synonyms": synonyms,
    }


def load_ingested_descriptor_uis(
    path: Path,
    *,
    allowlist_path: Path = _ALLOWLIST_PATH,
) -> frozenset[str]:
    """Descriptor UIs that the nih-mesh adapter would ingest from path."""
    allowlist = load_allowlist(allowlist_path)
    return frozenset(
        record["descriptor_ui"]
        for record in iter_descriptor_records(path)
        if record["descriptor_ui"]
        and matches_allowlist(record["tree_numbers"], allowlist)
    )


def iter_descriptor_records(path: Path) -> Iterator[dict]:
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "DescriptorRecord":
            continue
        record = parse_descriptor_record(elem)
        elem.clear()
        if record["descriptor_ui"] and record["label"]:
            yield record


def tree_hierarchy_edges(
    tree: str,
    tree_to_ui: dict[str, str],
    descriptors: dict[str, dict],
) -> Iterator[dict]:
    """Emit at most one edge: owner(tree) → owner(parent(tree)).

    Edges come only from MeSH browse tree numbers. SeeRelatedDescriptor,
    concept-level relations, and literature gene mappings are out of scope.
    """
    child_ui = tree_to_ui.get(tree)
    if child_ui is None or child_ui not in descriptors:
        return

    parent = parent_tree(tree)
    if parent is None:
        return
    parent_ui = tree_to_ui.get(parent)
    if parent_ui is None or parent_ui not in descriptors:
        return

    yield {
        "row_kind": "edge",
        "subject_id": child_ui,
        "object_id": parent_ui,
        "tree_number": tree,
        "predicate_id": PREDICATE_ID,
    }
