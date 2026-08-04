"""Classification rules document loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


class ClassificationRulesError(ValueError):
    """Raised when a classification-rules YAML is missing or malformed."""


@dataclass(frozen=True)
class EdgeMatchWhen:
    edge_class: str
    role: Literal["subject", "object"]


@dataclass(frozen=True)
class NodeMatchWhen:
    """Match merged nodes by optional @type and/or slot equality."""

    type_name: str | None = None
    slot: str | None = None
    equals: Any = None


@dataclass(frozen=True)
class AnnotateAction:
    target_entity: str
    slot: str
    value: str


@dataclass(frozen=True)
class AnnotateMapAction:
    target_entity: str
    slot: str
    from_slot: str
    value_map: dict[str, str]
    # When set (edge rules), read from_slot from this edge endpoint instead of the target.
    from_role: Literal["subject", "object"] | None = None


@dataclass(frozen=True)
class PropagateRestrictionsAction:
    from_class: str
    property_map: dict[str, str]


@dataclass(frozen=True)
class EmitEdgeAction:
    """Stub for Phase 2 relationship-view emission."""

    edge_class: str
    predicate: str
    object_template: str


Action = (
    AnnotateAction
    | AnnotateMapAction
    | PropagateRestrictionsAction
    | EmitEdgeAction
)


@dataclass(frozen=True)
class ClassificationRule:
    id: str
    when: EdgeMatchWhen | NodeMatchWhen
    actions: tuple[Action, ...]


@dataclass(frozen=True)
class ClassificationRulesDocument:
    version: int
    rules: tuple[ClassificationRule, ...]


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ClassificationRulesError(f"{field} must be a mapping")
    return value


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClassificationRulesError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_edge_when(raw: dict[str, Any], field: str) -> EdgeMatchWhen:
    edge_class = _require_str(raw.get("class"), f"{field}.class")
    role = _require_str(raw.get("role"), f"{field}.role")
    if role not in ("subject", "object"):
        raise ClassificationRulesError(
            f"{field}.role must be 'subject' or 'object', got {role!r}"
        )
    return EdgeMatchWhen(edge_class=edge_class, role=role)  # type: ignore[arg-type]


def _parse_when(raw: Any, field: str) -> EdgeMatchWhen | NodeMatchWhen:
    when = _require_mapping(raw, field)
    if "edge" in when:
        return _parse_edge_when(_require_mapping(when["edge"], f"{field}.edge"), f"{field}.edge")
    if "node" in when:
        node = _require_mapping(when["node"], f"{field}.node")
        type_name = node.get("@type")
        if type_name is not None:
            type_name = _require_str(type_name, f"{field}.node.@type")
        slot = node.get("slot")
        if slot is not None:
            slot = _require_str(slot, f"{field}.node.slot")
        return NodeMatchWhen(
            type_name=type_name,
            slot=slot,
            equals=node.get("equals"),
        )
    raise ClassificationRulesError(f"{field} must include edge or node")


def _parse_action(raw: Any, field: str) -> Action:
    action = _require_mapping(raw, field)
    if "annotate" in action:
        annotate = _require_mapping(action["annotate"], f"{field}.annotate")
        return AnnotateAction(
            target_entity=_require_str(
                annotate.get("target_entity"), f"{field}.annotate.target_entity"
            ),
            slot=_require_str(annotate.get("slot"), f"{field}.annotate.slot"),
            value=_require_str(annotate.get("value"), f"{field}.annotate.value"),
        )
    if "annotate_map" in action:
        annotate_map = _require_mapping(action["annotate_map"], f"{field}.annotate_map")
        value_map_raw = annotate_map.get("map")
        if not isinstance(value_map_raw, dict) or not value_map_raw:
            raise ClassificationRulesError(
                f"{field}.annotate_map.map must be a non-empty mapping"
            )
        value_map = {
            _require_str(key, f"{field}.annotate_map.map key"): _require_str(
                value, f"{field}.annotate_map.map[{key}]"
            )
            for key, value in value_map_raw.items()
        }
        from_role_raw = annotate_map.get("from_role")
        from_role: Literal["subject", "object"] | None = None
        if from_role_raw is not None:
            from_role_str = _require_str(
                from_role_raw, f"{field}.annotate_map.from_role"
            )
            if from_role_str not in ("subject", "object"):
                raise ClassificationRulesError(
                    f"{field}.annotate_map.from_role must be 'subject' or 'object', "
                    f"got {from_role_str!r}"
                )
            from_role = from_role_str  # type: ignore[assignment]
        return AnnotateMapAction(
            target_entity=_require_str(
                annotate_map.get("target_entity"),
                f"{field}.annotate_map.target_entity",
            ),
            slot=_require_str(annotate_map.get("slot"), f"{field}.annotate_map.slot"),
            from_slot=_require_str(
                annotate_map.get("from_slot"), f"{field}.annotate_map.from_slot"
            ),
            value_map=value_map,
            from_role=from_role,
        )
    if "propagate_restrictions" in action:
        propagate = _require_mapping(
            action["propagate_restrictions"], f"{field}.propagate_restrictions"
        )
        property_map_raw = propagate.get("property_map")
        if not isinstance(property_map_raw, dict) or not property_map_raw:
            raise ClassificationRulesError(
                f"{field}.propagate_restrictions.property_map must be a non-empty mapping"
            )
        property_map = {
            _require_str(key, f"{field}.propagate_restrictions.property_map key"): _require_str(
                value, f"{field}.propagate_restrictions.property_map[{key}]"
            )
            for key, value in property_map_raw.items()
        }
        return PropagateRestrictionsAction(
            from_class=_require_str(
                propagate.get("from_class"), f"{field}.propagate_restrictions.from_class"
            ),
            property_map=property_map,
        )
    if "emit_edge" in action:
        emit = _require_mapping(action["emit_edge"], f"{field}.emit_edge")
        return EmitEdgeAction(
            edge_class=_require_str(emit.get("class"), f"{field}.emit_edge.class"),
            predicate=_require_str(emit.get("predicate"), f"{field}.emit_edge.predicate"),
            object_template=_require_str(emit.get("object"), f"{field}.emit_edge.object"),
        )
    raise ClassificationRulesError(
        f"{field} must be annotate, annotate_map, propagate_restrictions, or emit_edge"
    )


def _parse_rule(raw: Any, field: str) -> ClassificationRule:
    rule = _require_mapping(raw, field)
    rule_id = _require_str(rule.get("id"), f"{field}.id")
    when = _parse_when(rule.get("when"), f"{field}.when")
    actions_raw = rule.get("actions")
    if not isinstance(actions_raw, list) or not actions_raw:
        raise ClassificationRulesError(f"{field}.actions must be a non-empty list")
    actions = tuple(
        _parse_action(action, f"{field}.actions[{i}]") for i, action in enumerate(actions_raw)
    )
    return ClassificationRule(id=rule_id, when=when, actions=actions)


def load_rules(path: Path) -> ClassificationRulesDocument:
    """Load and validate an actions-based classification rules document."""
    if not path.is_file():
        raise ClassificationRulesError(f"classification rules not found: {path}")

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    root = _require_mapping(data, "classification rules root")
    try:
        version = int(root["version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ClassificationRulesError(
            "classification rules missing required field: version"
        ) from exc

    rules_raw = root.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise ClassificationRulesError("classification rules.rules must be a non-empty list")

    rules = tuple(_parse_rule(rule, f"rules[{i}]") for i, rule in enumerate(rules_raw))
    return ClassificationRulesDocument(version=version, rules=rules)
