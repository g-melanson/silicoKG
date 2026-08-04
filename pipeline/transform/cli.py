import argparse
from datetime import datetime, timezone

from pipeline.transform.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Transform bronze records into silver fragments")
    parser.add_argument("--source-row-class", type=str, required=True)
    parser.add_argument("--source", type=str, required=True)
    parser.add_argument("--source-name", type=str, required=True)
    parser.add_argument("--bronze-run-id", type=str, required=True)
    parser.add_argument(
        "--run-id",
        type=str,
        default=datetime.now(timezone.utc).isoformat(),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of processes for bronze line-range sharding (default: 1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N bronze records (dev/benchmark)",
    )

    args = parser.parse_args()
    exit_code = run(
        source_row_class=args.source_row_class,
        source=args.source,
        source_name=args.source_name,
        bronze_run_id=args.bronze_run_id,
        run_id=args.run_id,
        workers=args.workers,
        limit=args.limit,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
