from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from pipeline.identity.fragments import build_fragment_envelope, build_quarantine_line
from pipeline.io.jsonl import JsonlWriter
from pipeline.transform.context import TransformContext
from pipeline.transform.engine import (
    TransformSummary,
    count_bronze_lines,
    transform_stream,
)
from pipeline.transform.reference import chromosome_represented_by_fragments

# Sources that emit static reference edges once per run (not per bronze row).
STATIC_REFERENCE_EDGE_SOURCES = frozenset({"ncbi-gene-info"})


def _append_static_reference_edges(
    *,
    source_name: str,
    fragments_path: Path,
    run_id: str,
) -> int:
    """Append once-per-run ChromosomeRepresentedBy fragments; return count added."""
    if source_name not in STATIC_REFERENCE_EDGE_SOURCES:
        return 0
    edges = chromosome_represented_by_fragments()
    if not edges:
        return 0
    with JsonlWriter(fragments_path, mode="ab") as out:
        for edge in edges:
            out.write(
                build_fragment_envelope(
                    target_class="ChromosomeRepresentedBy",
                    obj=edge,
                    source_name=source_name,
                    silver_run_id=run_id,
                    bronze_line=-1,
                    bronze_record={"tax_id": "9606"},
                )
            )
    return len(edges)


def _merge_summaries(parts: list[TransformSummary]) -> TransformSummary:
    merged = TransformSummary()
    for part in parts:
        merged.input_record_count += part.input_record_count
        merged.accepted_count += part.accepted_count
        merged.rejected_count += part.rejected_count
        for key, count in part.error_counts.items():
            merged.error_counts[key] = merged.error_counts.get(key, 0) + count
    return merged


def _write_stream_shard(
    *,
    source_row_class: str,
    bronze_records_path: Path,
    source_schema_path: Path,
    transform_schema_path: Path,
    source_name: str,
    run_id: str,
    fragments_path: Path,
    quarantine_path: Path,
    start: int = 0,
    end: int | None = None,
    limit: int | None = None,
) -> TransformSummary:
    summary = TransformSummary()
    with JsonlWriter(fragments_path) as frag_out, JsonlWriter(quarantine_path) as q_out:
        for outcome in transform_stream(
            source_row_class=source_row_class,
            bronze_records_path=bronze_records_path,
            source_schema_path=source_schema_path,
            transform_schema_path=transform_schema_path,
            source_name=source_name,
            start=start,
            end=end,
            limit=limit,
        ):
            if isinstance(outcome, TransformSummary):
                summary = outcome
                continue
            if outcome.accepted:
                frag_out.write(
                    build_fragment_envelope(
                        target_class=outcome.target_class,
                        obj=outcome.record,
                        source_name=source_name,
                        silver_run_id=run_id,
                        bronze_line=outcome.line_number,
                        bronze_record=outcome.bronze_record,
                    )
                )
            else:
                q_out.write(
                    build_quarantine_line(
                        bronze_line=outcome.line_number,
                        target_class=outcome.target_class,
                        bronze_record=outcome.bronze_record,
                        errors=outcome.errors,
                    )
                )
    return summary


def _worker_shard(payload: dict) -> dict:
    summary = _write_stream_shard(
        source_row_class=payload["source_row_class"],
        bronze_records_path=Path(payload["bronze_records_path"]),
        source_schema_path=Path(payload["source_schema_path"]),
        transform_schema_path=Path(payload["transform_schema_path"]),
        source_name=payload["source_name"],
        run_id=payload["run_id"],
        fragments_path=Path(payload["fragments_path"]),
        quarantine_path=Path(payload["quarantine_path"]),
        start=payload["start"],
        end=payload["end"],
        limit=payload.get("limit"),
    )
    return {
        "input_record_count": summary.input_record_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "error_counts": summary.error_counts,
        "part_index": payload["part_index"],
    }


def _concat_parts(part_paths: list[Path], dest: Path) -> None:
    with dest.open("wb") as out:
        for part in part_paths:
            with part.open("rb") as src:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            part.unlink(missing_ok=True)


def _line_ranges(total_lines: int, workers: int) -> list[tuple[int, int]]:
    if total_lines <= 0:
        return [(0, 0)]
    workers = max(1, min(workers, total_lines))
    base, rem = divmod(total_lines, workers)
    ranges: list[tuple[int, int]] = []
    start = 0
    for i in range(workers):
        size = base + (1 if i < rem else 0)
        end = start + size
        ranges.append((start, end))
        start = end
    return ranges


def run(
    bronze_run_id: str,
    source_row_class: str,
    source_name: str,
    source: str,
    run_id: str,
    workers: int = 1,
    limit: int | None = None,
) -> int:
    ctx = TransformContext(
        run_id=run_id,
        source=source,
        source_name=source_name,
        bronze_run_id=bronze_run_id,
        workers=max(1, workers),
        limit=limit,
    )

    silver_dir = ctx.paths.silver_run_dir(ctx.source_name, ctx.run_id)
    silver_dir.mkdir(parents=True, exist_ok=True)

    bronze_path = ctx.paths.bronze_records(ctx.source_name, ctx.bronze_run_id)
    source_schema_path = ctx.paths.source_schema_path_for(ctx.source, ctx.source_name)
    transform_schema_path = ctx.paths.transform_schema_path_for(
        ctx.source, ctx.source_name
    )
    fragments_path = ctx.paths.silver_fragments(ctx.source_name, ctx.run_id)
    quarantine_path = ctx.paths.silver_quarantine(ctx.source_name, ctx.run_id)

    started_at = datetime.now(timezone.utc)

    if ctx.workers == 1:
        summary = _write_stream_shard(
            source_row_class=source_row_class,
            bronze_records_path=bronze_path,
            source_schema_path=source_schema_path,
            transform_schema_path=transform_schema_path,
            source_name=ctx.source_name,
            run_id=ctx.run_id,
            fragments_path=fragments_path,
            quarantine_path=quarantine_path,
            limit=ctx.limit,
        )
    else:
        total_lines = count_bronze_lines(bronze_path)
        if ctx.limit is not None:
            total_lines = min(total_lines, ctx.limit)
        ranges = _line_ranges(total_lines, ctx.workers)
        part_payloads = []
        frag_parts: list[Path] = []
        q_parts: list[Path] = []
        for i, (start, end) in enumerate(ranges):
            frag_part = silver_dir / f"fragments.part{i}.jsonl"
            q_part = silver_dir / f"quarantine.part{i}.jsonl"
            frag_parts.append(frag_part)
            q_parts.append(q_part)
            part_payloads.append(
                {
                    "part_index": i,
                    "start": start,
                    "end": end,
                    "source_row_class": source_row_class,
                    "bronze_records_path": str(bronze_path),
                    "source_schema_path": str(source_schema_path),
                    "transform_schema_path": str(transform_schema_path),
                    "source_name": ctx.source_name,
                    "run_id": ctx.run_id,
                    "fragments_path": str(frag_part),
                    "quarantine_path": str(q_part),
                }
            )
        summaries: list[TransformSummary] = []
        with ProcessPoolExecutor(max_workers=len(part_payloads)) as pool:
            results = list(pool.map(_worker_shard, part_payloads))
        results.sort(key=lambda item: item["part_index"])
        for item in results:
            summaries.append(
                TransformSummary(
                    input_record_count=item["input_record_count"],
                    accepted_count=item["accepted_count"],
                    rejected_count=item["rejected_count"],
                    error_counts=item["error_counts"],
                )
            )
        _concat_parts(frag_parts, fragments_path)
        _concat_parts(q_parts, quarantine_path)
        summary = _merge_summaries(summaries)

    static_edge_count = _append_static_reference_edges(
        source_name=ctx.source_name,
        fragments_path=fragments_path,
        run_id=ctx.run_id,
    )
    summary.accepted_count += static_edge_count

    ended_at = datetime.now(timezone.utc)
    duration_seconds = (ended_at - started_at).total_seconds()

    ctx.paths.silver_manifest(ctx.source_name, ctx.run_id).write_text(
        json.dumps(
            {
                "run_id": ctx.run_id,
                "bronze_run_id": ctx.bronze_run_id,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "duration_seconds": duration_seconds,
                "workers": ctx.workers,
                "limit": ctx.limit,
                "source_name": ctx.source_name,
                "stage": "transform",
                "tier": "silver",
                "fragment_envelope": "class/object/source",
                "fragments_path": str(fragments_path),
                "drift": {
                    "input_record_count": summary.input_record_count,
                    "accepted_count": summary.accepted_count,
                    "rejected_count": summary.rejected_count,
                    "error_counts": summary.error_counts,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if summary.accepted_count == 0:
        return 1
    return 0
