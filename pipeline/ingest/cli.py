"""CLI entrypoint for the ingest tier."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime

from pipeline.ingest.runner import run


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.ingest.cli",
        description="Run silicoKG source ingestion into universe staging.",
    )
    parser.add_argument(
        "--source",
        default="ncbi",
        help="Publisher / source family (default: ncbi)",
    )
    parser.add_argument(
        "--source-name",
        default="ncbi-gene-info",
        help="Registered adapter / config key (default: ncbi-gene-info)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Pipeline run id (default: UTC timestamp)",
    )
    parser.add_argument(
        "--snapshot-raw",
        action="store_true",
        help="Copy raw input into universe staging/raw/ for provenance",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return run(
        source=args.source,
        source_name=args.source_name,
        run_id=args.run_id or _default_run_id(),
        snapshot_raw=args.snapshot_raw,
    )


if __name__ == "__main__":
    sys.exit(main())
