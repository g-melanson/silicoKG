"""Ingest tier core: validate rows and write staging artifacts."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from pipeline.ingest.context import IngestContext
from pipeline.paths import REJECTS_JSONL
from pipeline.progress import track

log = logging.getLogger(__name__)


class RowError(Exception):
    """A single row failed validation or normalization."""


@dataclass
class IngestStats:
    parsed: int = 0
    written: int = 0
    rejected: int = 0
    skipped: int = 0


def _validate_row(row: dict, required_fields: tuple[str, ...]) -> None:
    for field in required_fields:
        if not row.get(field):
            raise RowError(f"missing required field: {field}")


def run(
    ctx: IngestContext,
    rows: Iterator[dict],
    *,
    required_fields: tuple[str, ...] = ("tax_id", "gene_id"),
) -> IngestStats:
    """Consume normalized rows and write staging outputs for one source run."""
    stats = IngestStats()
    staging_dir = ctx.paths.staging_run_dir(ctx.source_name, ctx.run_id)
    staging_dir.mkdir(parents=True, exist_ok=True)

    records_path = ctx.paths.staging_records(ctx.source_name, ctx.run_id)
    rejects_path = staging_dir / REJECTS_JSONL
    manifest_path = ctx.paths.staging_manifest(ctx.source_name, ctx.run_id)

    with (
        records_path.open("w", encoding="utf-8") as records_f,
        rejects_path.open("w", encoding="utf-8") as rejects_f,
    ):
        for row in track(rows, desc=f"ingest {ctx.source_name}", unit="rows"):
            stats.parsed += 1
            try:
                _validate_row(row, required_fields)
            except RowError as exc:
                stats.rejected += 1
                rejects_f.write(
                    json.dumps(
                        {"error": str(exc), "row": row},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                continue

            records_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            stats.written += 1

    if stats.rejected == 0:
        rejects_path.unlink(missing_ok=True)

    manifest = {
        "source": ctx.source,
        "source_name": ctx.source_name,
        "run_id": ctx.run_id,
        "completed_at": datetime.now(UTC).isoformat(),
        "stats": asdict(stats),
        "artifacts": {
            "records": str(records_path.relative_to(ctx.paths.root.parent))
            if records_path.is_relative_to(ctx.paths.root.parent)
            else str(records_path),
            "rejects": str(rejects_path.name) if stats.rejected else None,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log.info("wrote staging records to %s", records_path)
    return stats
