"""Ingest orchestration: config, I/O setup, adapter wiring, engine invocation."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from pipeline.ingest import engine
from pipeline.ingest.context import IngestContext
from pipeline.ingest.fetch import ensure_cached_download
from pipeline.paths import REPO_ROOT
from sources.registry import get_adapter

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).with_name("config.yaml")

def load_config(source_name: str, config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or CONFIG_PATH
    if not path.is_absolute():
        path = REPO_ROOT / path
    with path.open(encoding="utf-8") as f:
        all_config = yaml.safe_load(f) or {}
    try:
        return all_config[source_name]
    except KeyError as exc:
        raise KeyError(f"no ingest config for source: {source_name}") from exc


def resolve_raw_path(ctx: IngestContext, config: dict[str, Any]) -> Path:
    """Resolve publisher input to a local path (cache, download, or local file)."""
    url = config["url"]
    if url.startswith("local://"):
        return REPO_ROOT / url.removeprefix("local://")

    if url.startswith(("http://", "https://", "ftp://")):
        cache_dir = ctx.paths.source_cache_dir(ctx.source_name)
        ttl_seconds = int(config.get("ttl_seconds", 21600))
        raw_filename = config.get("raw_filename") or Path(url).name
        return ensure_cached_download(
            url,
            cache_dir,
            raw_filename,
            ttl_seconds=ttl_seconds,
            decompress=bool(config.get("decompress", True)),
        )

    raise NotImplementedError(f"unsupported url scheme: {url!r}")


def ensure_staging_dirs(ctx: IngestContext) -> None:
    ctx.paths.staging_run_dir(ctx.source_name, ctx.run_id).mkdir(parents=True, exist_ok=True)
    ctx.paths.staging_raw_dir(ctx.source_name, ctx.run_id).mkdir(parents=True, exist_ok=True)


def snapshot_raw_input(ctx: IngestContext, raw_path: Path, config: dict[str, Any]) -> Path:
    """Copy the resolved raw input into staging/raw/ for provenance."""
    raw_dir = ctx.paths.staging_raw_dir(ctx.source_name, ctx.run_id)
    dest = raw_dir / config.get("raw_filename", raw_path.name)
    shutil.copy2(raw_path, dest)
    return dest


def build_adapter(source_name: str):
    """Return the adapter that parses publisher input for this source."""
    return get_adapter(source_name)


def run(
    source: str,
    source_name: str,
    run_id: str,
    *,
    snapshot_raw: bool = False,
    config_path: Path | None = None,
) -> int:
    """Orchestrate a single-source ingest run. Returns a process exit code."""
    config = load_config(source_name, config_path=config_path)
    ctx = IngestContext(
        run_id=run_id,
        source=source,
        source_name=source_name,
    )

    try:
        raw_path = resolve_raw_path(ctx, config)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1

    if not raw_path.exists():
        log.error("raw input not found: %s", raw_path)
        return 1

    ensure_staging_dirs(ctx)
    if snapshot_raw:
        snapshot_raw_input(ctx, raw_path, config)

    adapter = build_adapter(source_name)
    stats = engine.run(
        ctx,
        adapter.parse(raw_path, ctx=ctx),
        required_fields=adapter.ingest_required_fields,
    )

    log.info(
        "%s ingest complete: parsed=%d written=%d rejected=%d skipped=%d",
        source_name,
        stats.parsed,
        stats.written,
        stats.rejected,
        stats.skipped,
    )
    if stats.rejected and config.get("allow_rejects"):
        log.warning(
            "%s: %d rows rejected (allow_rejects=true); continuing with %d written rows",
            source_name,
            stats.rejected,
            stats.written,
        )
        return 0 if stats.written else 1
    return 0 if stats.rejected == 0 else 1
