"""Classify merged nodes from graph evidence + compiled OWL index."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Hashable, Iterator

from pipeline.ontology.classify.rules import (
    AnnotateAction,
    AnnotateMapAction,
    ClassificationRule,
    ClassificationRulesDocument,
    EdgeMatchWhen,
    EmitEdgeAction,
    NodeMatchWhen,
    PropagateRestrictionsAction,
    load_rules,
)
from pipeline.ontology.index import CompiledIndex, load_index
from pipeline.progress import iter_indexed_jsonl

log = logging.getLogger(__name__)

UNMAPPED_SLOT_VALUES_CAP = 20


class ClassifyError(ValueError):
    """Raised when classification cannot proceed (bad rules / missing classes)."""


@dataclass
class ClassifySummary:
    annotated_node_count: int = 0
    quarantined_stub_count: int = 0
    rule_match_counts: dict[str, int] = field(default_factory=dict)
    missing_filler_warnings: list[str] = field(default_factory=list)
    quarantined_missing_endpoints: list[dict[str, str]] = field(default_factory=list)
    unmapped_slot_value_count: int = 0
    unmapped_slot_values: list[str] = field(default_factory=list)
    index_hash: str = ""
    index_path: str = ""
    rules_path: str = ""


def _iter_jsonl(path: Path, *, desc: str) -> Iterator[dict[str, Any]]:
    for _line_number, record in iter_indexed_jsonl(path, desc=desc, loads=json.loads):
        yield record


def _dedup_key(item: Any) -> Hashable:
    if isinstance(item, dict):
        return tuple((k, _dedup_key(item[k])) for k in sorted(item))
    if isinstance(item, list):
        return tuple(_dedup_key(v) for v in item)
    return str(item)


def append_slot_value(node: dict[str, Any], slot: str, value: Any) -> bool:
    """Append ``value`` to a multivalued slot, deduping while preserving order.

    Returns True when the slot changed.
    """
    existing = node.get(slot)
    if existing is None:
        items: list[Any] = []
    elif isinstance(existing, list):
        items = list(existing)
    else:
        items = [existing]

    seen = {_dedup_key(item) for item in items}
    key = _dedup_key(value)
    if key in seen:
        node[slot] = items
        return False
    items.append(value)
    node[slot] = items
    return True


def _annotate_target_entity(rule: ClassificationRule) -> str | None:
    for action in rule.actions:
        if isinstance(action, (AnnotateAction, AnnotateMapAction)):
            return action.target_entity
    return None


def _requires_ontology_index(curie: str) -> bool:
    """silicoKG-owned class-label CURIEs are not part of the SO/OWL index."""
    return not curie.startswith("silkg:")


def _collect_required_classes(rules: ClassificationRulesDocument) -> set[str]:
    required: set[str] = set()
    for rule in rules.rules:
        for action in rule.actions:
            if isinstance(action, AnnotateAction):
                if _requires_ontology_index(action.value):
                    required.add(action.value)
            elif isinstance(action, AnnotateMapAction):
                required.update(
                    value
                    for value in action.value_map.values()
                    if _requires_ontology_index(value)
                )
            elif isinstance(action, PropagateRestrictionsAction):
                if _requires_ontology_index(action.from_class):
                    required.add(action.from_class)
    return required


def _preflight_index_classes(index: CompiledIndex, rules: ClassificationRulesDocument) -> None:
    missing = sorted(
        curie for curie in _collect_required_classes(rules) if curie not in index.classes
    )
    if missing:
        raise ClassifyError(
            "classification rules reference SO classes missing from index.classes: "
            + ", ".join(missing)
        )


def _record_unmapped(summary: ClassifySummary, value: str) -> None:
    summary.unmapped_slot_value_count += 1
    if value not in summary.unmapped_slot_values:
        if len(summary.unmapped_slot_values) < UNMAPPED_SLOT_VALUES_CAP:
            summary.unmapped_slot_values.append(value)


def _match_node_targets(
    rule: ClassificationRule,
    nodes: list[dict[str, Any]],
) -> list[str]:
    when = rule.when
    if not isinstance(when, NodeMatchWhen):
        return []

    targets: list[str] = []
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        if when.type_name is not None and node.get("@type") != when.type_name:
            continue
        if when.slot is not None and node.get(when.slot) != when.equals:
            continue
        targets.append(node_id)
    return targets


def _iter_edge_matches(
    rule: ClassificationRule,
    edges_by_class: dict[str, list[dict[str, Any]]],
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (target_id, edge) for each edge matching ``when.edge``."""
    when = rule.when
    if not isinstance(when, EdgeMatchWhen):
        return
    for edge in edges_by_class.get(when.edge_class, []):
        endpoint = edge.get(when.role)
        if isinstance(endpoint, str) and endpoint:
            yield endpoint, edge


def _source_value_for_annotate_map(
    action: AnnotateMapAction,
    *,
    target_node: dict[str, Any],
    edge: dict[str, Any] | None,
    nodes_by_id: dict[str, dict[str, Any]],
) -> Any:
    if action.from_role is None:
        return target_node.get(action.from_slot)

    if edge is None:
        log.warning(
            "annotate_map.from_role=%s requires an edge match; skipping",
            action.from_role,
        )
        return None

    source_id = edge.get(action.from_role)
    if not isinstance(source_id, str) or not source_id:
        return None
    source_node = nodes_by_id.get(source_id)
    if source_node is None:
        return None
    return source_node.get(action.from_slot)


def _apply_actions(
    node: dict[str, Any],
    rule: ClassificationRule,
    index: CompiledIndex,
    summary: ClassifySummary,
    *,
    edge: dict[str, Any] | None = None,
    nodes_by_id: dict[str, dict[str, Any]] | None = None,
) -> bool:
    changed = False
    nodes_by_id = nodes_by_id or {}
    for action in rule.actions:
        if isinstance(action, AnnotateAction):
            if append_slot_value(node, action.slot, action.value):
                changed = True
            continue

        if isinstance(action, AnnotateMapAction):
            raw_value = _source_value_for_annotate_map(
                action,
                target_node=node,
                edge=edge,
                nodes_by_id=nodes_by_id,
            )
            if raw_value is None or raw_value == "":
                continue
            keys = raw_value if isinstance(raw_value, list) else [raw_value]
            for key in keys:
                if key is None or key == "":
                    continue
                mapped = action.value_map.get(str(key))
                if mapped is None:
                    _record_unmapped(summary, str(key))
                    continue
                if append_slot_value(node, action.slot, mapped):
                    changed = True
            continue

        if isinstance(action, PropagateRestrictionsAction):
            restrictions = index.restrictions_index.get(action.from_class, [])
            for restriction in restrictions:
                property_id = restriction.get("property")
                filler = restriction.get("filler")
                if not property_id or not filler:
                    continue
                slot = action.property_map.get(property_id)
                if not slot:
                    continue
                if filler not in index.classes:
                    warning = (
                        f"{filler} filler for {action.from_class} "
                        f"via {property_id} not in index.classes"
                    )
                    if warning not in summary.missing_filler_warnings:
                        summary.missing_filler_warnings.append(warning)
                        log.warning(warning)
                if append_slot_value(node, slot, filler):
                    changed = True
            continue

        if isinstance(action, EmitEdgeAction):
            # Phase 2 — ignored
            continue

    return changed


def classify_merged_paths(
    nodes_path: Path,
    edges_path: Path,
    *,
    index_path: Path,
    rules_path: Path,
    index: CompiledIndex | None = None,
    rules: ClassificationRulesDocument | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], ClassifySummary]:
    """Annotate merged nodes in memory from rules + ontology index."""
    compiled = index or load_index(index_path)
    document = rules or load_rules(rules_path)
    _preflight_index_classes(compiled, document)

    nodes = list(_iter_jsonl(nodes_path, desc="classify nodes"))
    nodes_by_id = {node["id"]: node for node in nodes if "id" in node}
    edges = list(_iter_jsonl(edges_path, desc="classify edges"))

    edges_by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edge_class = edge.get("@type")
        if isinstance(edge_class, str):
            edges_by_class[edge_class].append(edge)

    summary = ClassifySummary(
        index_hash=compiled.input_hash,
        index_path=str(index_path),
        rules_path=str(rules_path),
    )
    annotated_ids: set[str] = set()
    quarantine_stubs: list[dict[str, Any]] = []
    quarantined_ids: set[str] = set()

    for rule in document.rules:
        target_entity = _annotate_target_entity(rule)
        match_count = 0

        if isinstance(rule.when, NodeMatchWhen):
            targets = _match_node_targets(rule, nodes)
            for target_id in targets:
                node = nodes_by_id.get(target_id)
                if node is None:
                    continue
                if target_entity is not None and node.get("@type") != target_entity:
                    continue
                match_count += 1
                if _apply_actions(
                    node, rule, compiled, summary, nodes_by_id=nodes_by_id
                ):
                    annotated_ids.add(target_id)
            summary.rule_match_counts[rule.id] = match_count
            continue

        for target_id, edge in _iter_edge_matches(rule, edges_by_class):
            node = nodes_by_id.get(target_id)
            if node is None:
                if target_id not in quarantined_ids:
                    stub_type = target_entity or "Gene"
                    stub = {"id": target_id, "@type": stub_type}
                    quarantine_stubs.append(stub)
                    quarantined_ids.add(target_id)
                    summary.quarantined_missing_endpoints.append(
                        {
                            "id": target_id,
                            "@type": stub_type,
                            "rule_id": rule.id,
                        }
                    )
                    log.warning(
                        "classify missing endpoint %s for rule %s; quarantined stub",
                        target_id,
                        rule.id,
                    )
                continue

            if target_entity is not None and node.get("@type") != target_entity:
                continue

            match_count += 1
            if _apply_actions(
                node,
                rule,
                compiled,
                summary,
                edge=edge,
                nodes_by_id=nodes_by_id,
            ):
                annotated_ids.add(target_id)

        summary.rule_match_counts[rule.id] = match_count

    summary.annotated_node_count = len(annotated_ids)
    summary.quarantined_stub_count = len(quarantine_stubs)
    # Preserve original node order; annotate in-place via nodes_by_id aliases.
    return nodes, quarantine_stubs, summary
