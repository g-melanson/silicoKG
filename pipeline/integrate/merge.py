"""Priority-aware node merge for integrate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable

from pipeline.identity.constants import MULTIVALUED_NODE_SLOTS, RESERVED_NODE_KEYS
from pipeline.identity.fragments import ensure_edge_predicate
from pipeline.integrate.priorities import IntegratePriorities

Contribution = tuple[str, dict, dict]


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _dedup_key(item: Any) -> Hashable:
    """Stable hashable key for multivalued-slot dedup (avoids json.dumps)."""
    if isinstance(item, dict):
        return tuple((k, _dedup_key(item[k])) for k in sorted(item))
    if isinstance(item, list):
        return tuple(_dedup_key(v) for v in item)
    return str(item)


def _rank(source_name: str, priorities: IntegratePriorities) -> int:
    return priorities.source_rank(source_name)


def _contribution_slot_rank(
    source_name: str,
    class_name: str,
    slot: str,
    priorities: IntegratePriorities,
) -> tuple[int, int]:
    override = priorities.slot_source_order(class_name, slot)
    if override:
        rank_map = {name: len(override) - idx for idx, name in enumerate(override)}
        return (rank_map.get(source_name, 0), _rank(source_name, priorities))
    return (0, _rank(source_name, priorities))


@dataclass
class NodeMergeState:
    """Incremental merge state for one node (fold while reading silver)."""

    node_id: str
    class_name: str
    slots: dict[str, Any] = field(default_factory=dict)
    scalar_ranks: dict[str, tuple[int, int]] = field(default_factory=dict)
    scalar_sources: dict[str, str] = field(default_factory=dict)
    multivalued_seen: dict[str, set[Hashable]] = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)
    alternates: list[dict] = field(default_factory=list)

    @classmethod
    def empty(cls, node_id: str, class_name: str) -> NodeMergeState:
        return cls(node_id=node_id, class_name=class_name)

    def add_provenance(self, source_name: str, source_meta: dict) -> None:
        self.sources.append(
            {
                "source_name": source_name,
                "silver_run_id": source_meta.get("silver_run_id"),
                "bronze_line": source_meta.get("bronze_line"),
            }
        )

    def apply_scalar(
        self,
        slot: str,
        value: Any,
        source_name: str,
        priorities: IntegratePriorities,
    ) -> None:
        new_rank = _contribution_slot_rank(source_name, self.class_name, slot, priorities)
        old_rank = self.scalar_ranks.get(slot)
        if old_rank is None:
            self.slots[slot] = value
            self.scalar_ranks[slot] = new_rank
            self.scalar_sources[slot] = source_name
            return

        if new_rank > old_rank:
            old_value = self.slots[slot]
            old_source = self.scalar_sources[slot]
            if old_value != value:
                self.alternates.append(
                    {"slot": slot, "value": old_value, "source": old_source}
                )
            self.slots[slot] = value
            self.scalar_ranks[slot] = new_rank
            self.scalar_sources[slot] = source_name
            return

        if value != self.slots[slot]:
            self.alternates.append(
                {"slot": slot, "value": value, "source": source_name}
            )

    def apply_multivalued(self, slot: str, value: Any) -> None:
        items = value if isinstance(value, list) else [value]
        merged = self.slots.setdefault(slot, [])
        seen = self.multivalued_seen.setdefault(slot, set())
        for item in items:
            key = _dedup_key(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)

    def to_dict(self) -> dict:
        merged: dict[str, Any] = {
            "id": self.node_id,
            "@type": self.class_name,
            **self.slots,
            "sources": self.sources,
        }
        if self.alternates:
            merged["alternates"] = self.alternates
        return merged


def apply_node_contribution(
    state: NodeMergeState | None,
    node_key: tuple[str, str],
    contribution: Contribution,
    priorities: IntegratePriorities,
) -> NodeMergeState:
    """Fold one silver node fragment into running merge state."""
    source_name, obj, source_meta = contribution
    node_id, class_name = node_key
    if state is None:
        state = NodeMergeState.empty(node_id, class_name)

    state.add_provenance(source_name, source_meta)
    for slot, value in obj.items():
        if slot in RESERVED_NODE_KEYS:
            continue
        if _is_empty(value):
            continue
        if slot in MULTIVALUED_NODE_SLOTS:
            state.apply_multivalued(slot, value)
        else:
            state.apply_scalar(slot, value, source_name, priorities)
    return state


def finalize_node(state: NodeMergeState | None) -> dict:
    if state is None:
        raise ValueError("cannot finalize empty node merge state")
    return state.to_dict()


def merge_node_fragments(
    node_key: tuple[str, str],
    contributions: list[Contribution],
    priorities: IntegratePriorities,
) -> dict:
    state: NodeMergeState | None = None
    for contribution in contributions:
        state = apply_node_contribution(state, node_key, contribution, priorities)
    return finalize_node(state)


def apply_edge_contribution(
    merged: dict | None,
    contribution: Contribution,
) -> dict:
    """Fold one silver edge fragment into running merge state."""
    if merged is None:
        return merge_edge_fragments([contribution])

    source_name, _obj, source_meta = contribution
    merged["sources"].append(
        {
            "source_name": source_name,
            "silver_run_id": source_meta.get("silver_run_id"),
            "bronze_line": source_meta.get("bronze_line"),
        }
    )
    return merged


def merge_edge_fragments(contributions: list[Contribution]) -> dict:
    merged = ensure_edge_predicate(dict(contributions[0][1]))
    merged["sources"] = [
        {
            "source_name": source_name,
            "silver_run_id": source_meta.get("silver_run_id"),
            "bronze_line": source_meta.get("bronze_line"),
        }
        for source_name, _obj, source_meta in contributions
    ]
    return merged
