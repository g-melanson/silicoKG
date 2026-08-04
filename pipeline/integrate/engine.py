"""Stream silver fragments and merge into nodes and edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pipeline.identity.constants import EDGE_CLASS_TO_PREDICATE
from pipeline.identity.fragments import ensure_edge_predicate
from pipeline.integrate.classify import (
    is_edge_class,
    validate_edge_object,
    validate_envelope,
)
from pipeline.integrate.merge import (
    NodeMergeState,
    apply_edge_contribution,
    apply_node_contribution,
    finalize_node,
)
from pipeline.integrate.priorities import IntegratePriorities
from pipeline.io.jsonl import loads_line
from pipeline.progress import iter_file_lines, track


@dataclass
class IntegrateSummary:
    fragment_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    quarantine_count: int = 0
    sources: list[str] = field(default_factory=list)


def _edge_key(obj: dict) -> tuple[str, str, str, str]:
    obj = ensure_edge_predicate(obj)
    edge_type = obj.get("@type") or ""
    predicate = obj.get("predicate") or EDGE_CLASS_TO_PREDICATE.get(edge_type) or ""
    return (
        edge_type,
        obj.get("subject") or "",
        predicate,
        obj.get("object") or "",
    )


def integrate_silver_paths(
    fragment_paths: list[Path],
    priorities: IntegratePriorities,
) -> tuple[list[dict], list[dict], list[dict], IntegrateSummary]:
    node_states: dict[tuple[str, str], NodeMergeState] = {}
    edge_states: dict[tuple[str, str, str, str], dict] = {}
    id_to_type: dict[str, str] = {}
    quarantine: list[dict] = []
    summary = IntegrateSummary(sources=[str(p) for p in fragment_paths])

    for path in fragment_paths:
        desc = f"integrate {path.parent.name}"
        for line in iter_file_lines(path, desc=desc):
            if not line.strip():
                continue
            summary.fragment_count += 1
            fragment = loads_line(line)
            errors = validate_envelope(fragment)
            if errors:
                quarantine.append({"fragment": fragment, "errors": errors})
                summary.quarantine_count += 1
                continue

            class_name = fragment["class"]
            obj = fragment["object"]
            source_name = fragment["source"]["source_name"]
            contribution = (source_name, obj, fragment["source"])

            node_id = obj.get("id")
            node_type = obj.get("@type")

            if is_edge_class(class_name, obj):
                edge_errors = validate_edge_object(obj)
                if edge_errors:
                    quarantine.append(
                        {"fragment": fragment, "errors": edge_errors}
                    )
                    summary.quarantine_count += 1
                    continue
                key = _edge_key(obj)
                edge_states[key] = apply_edge_contribution(
                    edge_states.get(key),
                    contribution,
                )
                continue

            if not node_id or not node_type:
                quarantine.append(
                    {
                        "fragment": fragment,
                        "errors": ["node fragment missing id or @type"],
                    }
                )
                summary.quarantine_count += 1
                continue

            existing_type = id_to_type.get(node_id)
            if existing_type is not None and existing_type != node_type:
                quarantine.append(
                    {
                        "fragment": fragment,
                        "errors": [
                            f"type conflict for id {node_id!r}: "
                            f"{existing_type!r} vs {node_type!r}"
                        ],
                    }
                )
                summary.quarantine_count += 1
                continue

            id_to_type.setdefault(node_id, node_type)
            node_key = (node_id, node_type)
            node_states[node_key] = apply_node_contribution(
                node_states.get(node_key),
                node_key,
                contribution,
                priorities,
            )

    nodes = [
        finalize_node(state)
        for _key, state in track(
            sorted(node_states.items(), key=lambda item: item[0]),
            total=len(node_states),
            desc="finalize nodes",
            unit="nodes",
        )
    ]
    edges = [
        edge
        for _key, edge in track(
            sorted(edge_states.items(), key=lambda item: item[0]),
            total=len(edge_states),
            desc="finalize edges",
            unit="edges",
        )
    ]

    summary.node_count = len(nodes)
    summary.edge_count = len(edges)
    return nodes, edges, quarantine, summary
