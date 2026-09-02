"""Classify merged nodes from graph evidence + compiled OWL index."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Hashable, Iterator

from pipeline.io.jsonl import loads_line
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
class ClassifyGraph:
    """Working set. Nodes stay listed (rewrite order). Edges exist only by @type."""

    nodes: list[dict[str, Any]]
    nodes_by_id: dict[str, dict[str, Any]]
    edges_by_class: dict[str, list[dict[str, Any]]]


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


@dataclass(frozen=True)
class ActionContext:
    """Everything an action handler may read beyond the target node."""

    index: CompiledIndex
    summary: ClassifySummary
    nodes_by_id: dict[str, dict[str, Any]]
    edge: dict[str, Any] | None = None


def _iter_jsonl(path: Path, *, desc: str) -> Iterator[dict[str, Any]]:
    for _line_number, record in iter_indexed_jsonl(path, desc=desc, loads=loads_line):
        yield record


def _dedup_key(item: Any) -> Hashable:
    if isinstance(item, dict):
        return tuple((k, _dedup_key(item[k])) for k in sorted(item))
    if isinstance(item, list):
        return tuple(_dedup_key(v) for v in item)
    return str(item)


def append_slot_value(node: dict[str, Any], slot: str, value: Any) -> bool:
    """Append ``value`` to a multivalued slot, deduping while preserving order.

    Returns True when the slot changed. A duplicate leaves the node untouched,
    so re-running classify does not rewrite (or re-list) already-annotated slots.
    """
    existing = node.get(slot)
    if existing is None:
        items: list[Any] = []
    elif isinstance(existing, list):
        items = existing
    else:
        items = [existing]

    key = _dedup_key(value)
    if any(_dedup_key(item) == key for item in items):
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


def _record_missing_filler(
    summary: ClassifySummary, from_class: str, property_id: str, filler: str
) -> None:
    warning = f"{filler} filler for {from_class} via {property_id} not in index.classes"
    if warning in summary.missing_filler_warnings:
        return
    summary.missing_filler_warnings.append(warning)
    log.warning(warning)


def _quarantine_missing(
    target_id: str,
    target_entity: str | None,
    rule_id: str,
    quarantine: list[dict[str, Any]],
    quarantined_ids: set[str],
    summary: ClassifySummary,
) -> None:
    if target_id in quarantined_ids:
        return
    if target_entity is None:
        raise ClassifyError(
            f"rule {rule_id} matched missing endpoint {target_id} but declares no "
            "target_entity; cannot type the quarantine stub"
        )

    quarantine.append({"id": target_id, "@type": target_entity})
    quarantined_ids.add(target_id)
    summary.quarantined_missing_endpoints.append(
        {"id": target_id, "@type": target_entity, "rule_id": rule_id}
    )
    log.warning(
        "classify missing endpoint %s for rule %s; quarantined stub",
        target_id,
        rule_id,
    )


def _iter_matches(
    rule: ClassificationRule,
    graph: ClassifyGraph,
    quarantine: list[dict[str, Any]],
    quarantined_ids: set[str],
    summary: ClassifySummary,
) -> Iterator[tuple[dict[str, Any], dict[str, Any] | None]]:
    """Yield (target node, edge) for each node this rule should annotate."""
    target_entity = _annotate_target_entity(rule)
    when = rule.when

    if isinstance(when, NodeMatchWhen):
        for node in graph.nodes:
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                continue
            if when.type_name is not None and node.get("@type") != when.type_name:
                continue
            if when.slot is not None and node.get(when.slot) != when.equals:
                continue
            if target_entity is not None and node.get("@type") != target_entity:
                continue
            yield node, None
        return

    if not isinstance(when, EdgeMatchWhen):
        raise ClassifyError(f"rule {rule.id} has an unsupported match clause")

    for edge in graph.edges_by_class.get(when.edge_class, []):
        target_id = edge.get(when.role)
        if not isinstance(target_id, str) or not target_id:
            continue

        node = graph.nodes_by_id.get(target_id)
        if node is None:
            _quarantine_missing(
                target_id, target_entity, rule.id, quarantine, quarantined_ids, summary
            )
            continue

        if target_entity is not None and node.get("@type") != target_entity:
            continue
        yield node, edge


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


def _apply_annotate(
    node: dict[str, Any], action: AnnotateAction, ctx: ActionContext
) -> bool:
    return append_slot_value(node, action.slot, action.value)


def _apply_annotate_map(
    node: dict[str, Any], action: AnnotateMapAction, ctx: ActionContext
) -> bool:
    raw_value = _source_value_for_annotate_map(
        action,
        target_node=node,
        edge=ctx.edge,
        nodes_by_id=ctx.nodes_by_id,
    )
    if raw_value is None or raw_value == "":
        return False

    changed = False
    keys = raw_value if isinstance(raw_value, list) else [raw_value]
    for key in keys:
        if key is None or key == "":
            continue
        mapped = action.value_map.get(str(key))
        if mapped is None:
            _record_unmapped(ctx.summary, str(key))
            continue
        if append_slot_value(node, action.slot, mapped):
            changed = True
    return changed


def _apply_propagate_restrictions(
    node: dict[str, Any], action: PropagateRestrictionsAction, ctx: ActionContext
) -> bool:
    changed = False
    for restriction in ctx.index.restrictions_index.get(action.from_class, []):
        property_id = restriction.get("property")
        filler = restriction.get("filler")
        if not property_id or not filler:
            continue
        slot = action.property_map.get(property_id)
        if not slot:
            continue
        if filler not in ctx.index.classes:
            _record_missing_filler(ctx.summary, action.from_class, property_id, filler)
        if append_slot_value(node, slot, filler):
            changed = True
    return changed


def _apply_emit_edge(
    node: dict[str, Any], action: EmitEdgeAction, ctx: ActionContext
) -> bool:
    """Phase 2 — parsed by the rules loader, not yet emitted by the engine."""
    return False


ACTION_HANDLERS: dict[type, Callable[[dict[str, Any], Any, ActionContext], bool]] = {
    AnnotateAction: _apply_annotate,
    AnnotateMapAction: _apply_annotate_map,
    PropagateRestrictionsAction: _apply_propagate_restrictions,
    EmitEdgeAction: _apply_emit_edge,
}


def _apply_actions(
    node: dict[str, Any],
    rule: ClassificationRule,
    ctx: ActionContext,
) -> bool:
    changed = False
    for action in rule.actions:
        handler = ACTION_HANDLERS.get(type(action))
        if handler is None:
            raise ClassifyError(
                f"rule {rule.id} uses unsupported action {type(action).__name__}"
            )
        if handler(node, action, ctx):
            changed = True
    return changed


def _load_graph(nodes_path: Path, edges_path: Path) -> ClassifyGraph:
    """Load the working set: nodes in file order, edges only as a class index."""
    nodes = list(_iter_jsonl(nodes_path, desc="classify nodes"))
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        if node_id in nodes_by_id:
            raise ClassifyError(f"duplicate node id in merged nodes: {node_id}")
        nodes_by_id[node_id] = node

    # Edges are streamed straight into the index; the full edge list is never held.
    edges_by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in _iter_jsonl(edges_path, desc="classify edges"):
        edge_class = edge.get("@type")
        if isinstance(edge_class, str):
            edges_by_class[edge_class].append(edge)

    return ClassifyGraph(
        nodes=nodes,
        nodes_by_id=nodes_by_id,
        edges_by_class=edges_by_class,
    )


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

    graph = _load_graph(nodes_path, edges_path)
    summary = ClassifySummary(
        index_hash=compiled.input_hash,
        index_path=str(index_path),
        rules_path=str(rules_path),
    )
    annotated_ids: set[str] = set()
    quarantine_stubs: list[dict[str, Any]] = []
    quarantined_ids: set[str] = set()

    for rule in document.rules:
        match_count = 0
        for node, edge in _iter_matches(
            rule, graph, quarantine_stubs, quarantined_ids, summary
        ):
            match_count += 1
            ctx = ActionContext(
                index=compiled,
                summary=summary,
                nodes_by_id=graph.nodes_by_id,
                edge=edge,
            )
            if _apply_actions(node, rule, ctx):
                annotated_ids.add(node["id"])
        summary.rule_match_counts[rule.id] = match_count

    summary.annotated_node_count = len(annotated_ids)
    summary.quarantined_stub_count = len(quarantine_stubs)
    # Preserve original node order; annotation happened in-place on graph.nodes.
    return graph.nodes, quarantine_stubs, summary
