import argparse
from pathlib import Path

from pipeline.publish.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish merged tier to consumer-ready gold tier"
    )
    parser.add_argument("--run-id", required=True, help="Pipeline run id")
    parser.add_argument(
        "--merged-run-id",
        default=None,
        help="Run id to read merged tier from (default: same as --run-id)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Path to domain schema YAML",
    )
    args = parser.parse_args()
    exit_code = run(
        run_id=args.run_id,
        merged_run_id=args.merged_run_id,
        schema_path=args.schema,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
