import json
from datetime import datetime, timezone

from pipeline.ingest.runner import build_adapter
from pipeline.validate.context import ValidateContext
from pipeline.validate.engine import validate_records


def run(
    source: str,
    source_name: str,
    target_class: str,
    staging_run_id: str,
    run_id: str,
):
    adapter = build_adapter(source_name)
    target_class_for_record = getattr(adapter, "target_class_for_record", None)

    ctx = ValidateContext(
        run_id=run_id,
        source=source,
        source_name=source_name,
        target_class=target_class,
        staging_run_id=staging_run_id
    )
    ctx.paths.bronze_run_dir(ctx.source_name, ctx.run_id).mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)

    schema_path = ctx.paths.source_schema_path_for(ctx.source, ctx.source_name)

    validation_result = validate_records(
        records_path=ctx.paths.staging_records(ctx.source_name, ctx.staging_run_id),
        schema_path=schema_path,
        target_class=ctx.target_class,
        target_class_for_record=target_class_for_record,
    )

    with ctx.paths.bronze_records(ctx.source_name, ctx.run_id).open("w") as f:
        with ctx.paths.bronze_quarantine(ctx.source_name, ctx.run_id).open("w") as q:
            for record in validation_result.outcomes:

                if record.accepted: 
                    f.write(json.dumps(record.record) + "\n")

                else: 
                    q.write(json.dumps({
                        "record": record.record,
                        "errors": record.errors
                    }) + "\n")

    finished_at = datetime.now(timezone.utc)

    bronze_manifest = {
        "run_id": ctx.run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "source": ctx.source,
        "source_name": ctx.source_name,
        "target_class": ctx.target_class,
        "staging_run_id": ctx.staging_run_id,
        "stage": "validate",
        "tier": "bronze",
        "source_schema_path": str(schema_path),
        "records_path": str(ctx.paths.bronze_records(ctx.source_name, ctx.run_id)),
        "drift": {
            "input_record_count": validation_result.summary.input_record_count,
            "accepted_count": validation_result.summary.accepted_count,
            "rejected_count": validation_result.summary.rejected_count,
            "error_counts": validation_result.summary.error_counts,
        },
    }
    with ctx.paths.bronze_manifest(ctx.source_name, ctx.run_id).open("w") as f:
        json.dump(bronze_manifest, f, indent=2)

    return
