import argparse
from pathlib import Path

from pipeline.integrate.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Integrate silver fragments into merged tier")
    parser.add_argument("--run-id", required=True, help="Pipeline run id")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["ncbi-gene-info"],
        help="Source names whose silver fragments to merge",
    )
    parser.add_argument(
        "--priorities",
        type=Path,
        default=None,
        help="Path to integrate-priorities.yaml",
    )
    args = parser.parse_args()
    exit_code = run(
        run_id=args.run_id,
        source_names=args.sources,
        priorities_path=args.priorities,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
