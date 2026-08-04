"""CLI entrypoint for YAML-driven pipeline runs.

Stage CLIs (e.g. ``python -m pipeline.ingest.cli``) remain available for
single-stage use. This entrypoint only accepts a run-config YAML path.
"""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline.progress import configure
from pipeline.run.loader import PipelineRunConfigError, load_run_config
from pipeline.run.runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.run.cli",
        description="Run a silicoKG pipeline from a YAML run-context instance.",
    )
    parser.add_argument(
        "config",
        help="Path to a pipeline run YAML instance",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging (overrides YAML verbose when set)",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bars",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ctx = load_run_config(args.config)
    except PipelineRunConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verbose = args.verbose or ctx.verbose
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    configure(enabled=False if args.no_progress else ctx.progress)
    return run(ctx)


if __name__ == "__main__":
    sys.exit(main())
