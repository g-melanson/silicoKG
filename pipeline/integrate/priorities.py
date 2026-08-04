"""Load integrate priority configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pipeline.paths import REPO_ROOT

DEFAULT_PRIORITIES_PATH = REPO_ROOT / "schemas" / "integrate-priorities.yaml"


@dataclass(frozen=True)
class IntegratePriorities:
    source_ranks: dict[str, int]
    slot_overrides: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def source_rank(self, source_name: str) -> int:
        return self.source_ranks.get(source_name, 0)

    def slot_source_order(self, class_name: str, slot: str) -> list[str] | None:
        class_overrides = self.slot_overrides.get(class_name, {})
        return class_overrides.get(slot)


def load_priorities(path: Path | None = None) -> IntegratePriorities:
    priorities_path = path or DEFAULT_PRIORITIES_PATH
    with priorities_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return IntegratePriorities(
        source_ranks=data.get("sources", {}),
        slot_overrides=data.get("slots", {}),
    )
