"""CLI entrypoint for ontology index generation."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pipeline.config import parse_str_set
from pipeline.ontology.runner import (
    build_context,
    context_from_config,
    run,
    run_named,
    sync_index_from_rules,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.ontology.cli",
        description="Build a compiled ontology index from OWL.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_index = subparsers.add_parser(
        "build-index",
        help="Extract classes/restrictions from OWL and write index.yaml",
    )
    build_index.add_argument(
        "--source-name",
        help="Ontology config key (e.g. obo-so)",
    )
    build_index.add_argument(
        "--url",
        help="OWL file URL or local path (overrides config url)",
    )
    build_index.add_argument(
        "--source",
        help="Publisher / source family (required without --source-name)",
    )
    build_index.add_argument(
        "--ontology-namespace",
        help="Named class IRI prefix (required without --source-name)",
    )
    build_index.add_argument(
        "--term-id-prefix",
        help="CURIE prefix for class terms (required without --source-name)",
    )
    build_index.add_argument(
        "--property-namespace",
        help="Named property IRI prefix",
    )
    build_index.add_argument(
        "--property-id-prefix",
        help="CURIE prefix for property terms",
    )
    build_index.add_argument(
        "--term",
        action="append",
        default=[],
        help="Optional class IRI to include (repeatable). Omit for full extraction.",
    )
    build_index.add_argument(
        "--terms-file",
        type=Path,
        help="Optional file with one class IRI per line",
    )
    build_index.add_argument(
        "--output",
        type=Path,
        help="Output index path (default: universe/cache/{source_name}/index.yaml)",
    )
    build_index.add_argument(
        "--config",
        type=Path,
        help="Ontology config YAML path",
    )
    build_index.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    sync_index = subparsers.add_parser(
        "sync-index",
        help="Rebuild index from classification rules + SO label map CURIEs",
    )
    sync_index.add_argument(
        "--source-name",
        default="obo-so",
        help="Ontology config key (default: obo-so)",
    )
    sync_index.add_argument(
        "--rules",
        type=Path,
        help="Classification rules YAML (default: schemas/ontology/classification-rules.yaml)",
    )
    sync_index.add_argument(
        "--label-map",
        type=Path,
        help="SO label map YAML (default: schemas/ontology/so-label-map.yaml)",
    )
    sync_index.add_argument(
        "--output",
        type=Path,
        help="Output index path (default: universe/cache/{source_name}/index.yaml)",
    )
    sync_index.add_argument(
        "--config",
        type=Path,
        help="Ontology config YAML path",
    )
    sync_index.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def _terms_from_args(args: argparse.Namespace) -> frozenset[str] | None:
    terms = list(args.term)
    if args.terms_file is not None:
        with args.terms_file.open(encoding="utf-8") as handle:
            terms.extend(line.strip() for line in handle if line.strip())
    return parse_str_set(terms, field="terms") if terms else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        if args.command == "sync-index":
            from pipeline.export.neo4j.label_map import DEFAULT_LABEL_MAP_PATH
            from pipeline.ontology.classify.context import DEFAULT_RULES_PATH

            destination = sync_index_from_rules(
                args.source_name,
                rules_path=args.rules or DEFAULT_RULES_PATH,
                label_map_path=args.label_map or DEFAULT_LABEL_MAP_PATH,
                output_path=args.output,
                config_path=args.config,
            )
        else:
            terms = _terms_from_args(args)
            if args.source_name:
                destination = run_named(
                    args.source_name,
                    url=args.url,
                    terms=terms,
                    output_path=args.output,
                    config_path=args.config,
                )
            else:
                missing = [
                    flag
                    for flag, value in (
                        ("--url", args.url),
                        ("--source", args.source),
                        ("--ontology-namespace", args.ontology_namespace),
                        ("--term-id-prefix", args.term_id_prefix),
                    )
                    if not value
                ]
                if missing:
                    raise ValueError(
                        "either --source-name or all of "
                        f"{', '.join(missing)} are required"
                    )
                ctx = build_context(
                    source=args.source,
                    source_name=args.source_name or Path(args.url).stem,
                    url=args.url,
                    ontology_namespace=args.ontology_namespace,
                    term_id_prefix=args.term_id_prefix,
                    property_namespace=args.property_namespace,
                    property_id_prefix=args.property_id_prefix,
                    terms=terms,
                )
                destination = run(ctx, output_path=args.output)
    except (KeyError, ValueError, FileNotFoundError, RuntimeError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
