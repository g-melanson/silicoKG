"""Orchestrate pipeline stages from a YAML-loaded run context."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from pipeline.run.context import PipelineRunContext, SourceSpec
from pipeline.progress import write_message

log = logging.getLogger(__name__)

PER_SOURCE_STAGES = frozenset({"ingest", "validate", "transform"})
RUN_LEVEL_STAGES = frozenset({"integrate", "classify", "publish", "export_neo4j"})


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _run_ingest(ctx: PipelineRunContext, spec: SourceSpec, run_id: str) -> int:
    from pipeline.ingest.runner import run as ingest_run

    ingest_args = ctx.stage_args.get("ingest", {})
    config = ingest_args.get("config")
    config_path = Path(config) if config else None
    return ingest_run(
        source=spec.source,
        source_name=spec.source_name,
        run_id=run_id,
        snapshot_raw=bool(ingest_args.get("snapshot_raw", ctx.snapshot_raw)),
        config_path=config_path,
    )


def _run_validate(ctx: PipelineRunContext, spec: SourceSpec, run_id: str) -> int:
    from pipeline.ingest.runner import build_adapter
    from pipeline.validate.runner import run as validate_run

    adapter = build_adapter(spec.source_name)
    validate_args = ctx.stage_args.get("validate", {})
    staging_run_id = validate_args.get("staging_run_id", run_id)
    validate_run(
        source=spec.source,
        source_name=spec.source_name,
        target_class=adapter.target_class,
        staging_run_id=staging_run_id,
        run_id=run_id,
    )
    return 0


def _transform_kwargs(
    ctx: PipelineRunContext, spec: SourceSpec, run_id: str
) -> dict:
    from pipeline.ingest.runner import build_adapter

    adapter = build_adapter(spec.source_name)
    transform_args = ctx.stage_args.get("transform", {})
    bronze_run_id = transform_args.get("bronze_run_id", run_id)
    workers = int(transform_args.get("workers", 1))
    limit = transform_args.get("limit")
    if limit is not None:
        limit = int(limit)
    return {
        "bronze_run_id": bronze_run_id,
        "source_row_class": adapter.target_class,
        "source_name": spec.source_name,
        "source": spec.source,
        "run_id": run_id,
        "workers": workers,
        "limit": limit,
    }


def _run_transform(ctx: PipelineRunContext, spec: SourceSpec, run_id: str) -> int:
    from pipeline.transform.runner import run as transform_run

    return transform_run(**_transform_kwargs(ctx, spec, run_id))


def _transform_job(payload: dict) -> tuple[str, int]:
    from pipeline.transform.runner import run as transform_run

    source_name = payload["source_name"]
    return source_name, transform_run(**payload)


def _run_integrate(ctx: PipelineRunContext, run_id: str) -> int:
    from pipeline.integrate.runner import run as integrate_run

    integrate_args = ctx.stage_args.get("integrate", {})
    priorities = integrate_args.get("priorities")
    priorities_path = Path(priorities) if priorities else None
    source_names = [spec.source_name for spec in ctx.sources]
    return integrate_run(
        run_id=run_id,
        source_names=source_names,
        priorities_path=priorities_path,
    )


def _run_classify(ctx: PipelineRunContext, run_id: str) -> int:
    from pipeline.ontology.classify.runner import run as classify_run

    args = ctx.stage_args.get("classify", {})
    if "source_name" not in args:
        raise ValueError("classify.source_name is required")
    if "rules" not in args:
        raise ValueError("classify.rules is required")
    return classify_run(
        run_id=run_id,
        source_name=args["source_name"],
        rules_path=Path(args["rules"]),
        source=args.get("source"),
    )


def _run_publish(ctx: PipelineRunContext, run_id: str) -> int:
    from pipeline.publish.config import PublishConfig
    from pipeline.publish.runner import run as publish_run

    publish_args = ctx.stage_args.get("publish", {})
    merged_run_id = publish_args.get("merged_run_id", run_id)
    schema = publish_args.get("schema")
    schema_path = Path(schema) if schema else None
    config = PublishConfig.from_mapping(publish_args)
    return publish_run(
        run_id=run_id,
        merged_run_id=merged_run_id,
        schema_path=schema_path,
        config=config,
    )


def _run_export_neo4j(ctx: PipelineRunContext, run_id: str) -> int:
    from pipeline.export.neo4j.config import Neo4jExportConfig
    from pipeline.export.neo4j.runner import run as export_neo4j_run
    from pipeline.paths import DEFAULT_PATHS

    export_args = ctx.stage_args.get("export_neo4j", {})
    publish_args = ctx.stage_args.get("publish", {})
    gold_run_id = export_args.get("gold_run_id", run_id)
    config = Neo4jExportConfig.resolve(
        export_args,
        publish_raw=publish_args,
        gold_manifest_path=DEFAULT_PATHS.gold_manifest(gold_run_id),
    )
    return export_neo4j_run(run_id=run_id, gold_run_id=gold_run_id, config=config)


STAGE_HANDLERS = {
    "ingest": _run_ingest,
    "validate": _run_validate,
    "transform": _run_transform,
}


def _run_transforms_parallel(ctx: PipelineRunContext, run_id: str) -> int:
    payloads = [_transform_kwargs(ctx, spec, run_id) for spec in ctx.sources]
    log.info(
        "running transform for %s sources in parallel",
        len(payloads),
    )
    with ProcessPoolExecutor(max_workers=len(payloads)) as pool:
        futures = {pool.submit(_transform_job, payload): payload for payload in payloads}
        for future in as_completed(futures):
            source_name, code = future.result()
            if code:
                log.error("transform failed for %s (exit=%s)", source_name, code)
                for pending in futures:
                    pending.cancel()
                return code
    return 0


def run(ctx: PipelineRunContext) -> int:
    """Execute configured stages for each source. Returns a process exit code."""
    run_id = ctx.run_id or _default_run_id()
    log.info(
        "pipeline run %s: stages=%s sources=%s",
        run_id,
        list(ctx.stages),
        [(s.source, s.source_name) for s in ctx.sources],
    )

    transform_args = ctx.stage_args.get("transform", {})
    parallel_sources = bool(transform_args.get("parallel_sources", False))
    per_source_stages = [stage for stage in ctx.stages if stage in PER_SOURCE_STAGES]
    early_stages = [
        stage for stage in per_source_stages if not (parallel_sources and stage == "transform")
    ]
    run_transform_parallel = parallel_sources and "transform" in per_source_stages

    exit_code = 0
    for spec in ctx.sources:
        for stage in early_stages:
            write_message(f"running {stage} for {spec.source}/{spec.source_name}")
            log.info("running %s for %s/%s", stage, spec.source, spec.source_name)
            code = STAGE_HANDLERS[stage](ctx, spec, run_id)
            if code:
                exit_code = code
                log.error(
                    "%s failed for %s/%s (exit=%s)",
                    stage,
                    spec.source,
                    spec.source_name,
                    code,
                )
                return exit_code

    if run_transform_parallel:
        code = _run_transforms_parallel(ctx, run_id)
        if code:
            return code

    for stage in ctx.stages:
        if stage not in RUN_LEVEL_STAGES:
            continue
        write_message(f"running {stage} for run {run_id}")
        log.info("running %s for run %s", stage, run_id)
        if stage == "integrate":
            code = _run_integrate(ctx, run_id)
        elif stage == "classify":
            code = _run_classify(ctx, run_id)
        elif stage == "publish":
            code = _run_publish(ctx, run_id)
        elif stage == "export_neo4j":
            code = _run_export_neo4j(ctx, run_id)
        else:
            continue
        if code:
            exit_code = code
            log.error("%s failed for run %s (exit=%s)", stage, run_id, code)
            return exit_code

    log.info("pipeline run %s complete", run_id)
    return exit_code
