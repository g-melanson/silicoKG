"""CLI for ontology-driven merged-node classification."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.ontology.classify.context import DEFAULT_RULES_PATH, DEFAULT_SOURCE_NAME
from pipeline.ontology.classify.runner import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify merged nodes from ontology rules + OWL index"
    )
    parser.add_argument("--run-id", required=True, help="Pipeline run id")
    parser.add_argument(
        "--source-name",
        default=DEFAULT_SOURCE_NAME,
        help=f"Ontology cache source_name (default: {DEFAULT_SOURCE_NAME})",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES_PATH,
        help="Path to classification-rules.yaml",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional ontology source label for manifest metadata",
    )
    args = parser.parse_args(argv)
    return run(
        run_id=args.run_id,
        source_name=args.source_name,
        rules_path=args.rules,
        source=args.source,
    )


if __name__ == "__main__":
    raise SystemExit(main())
