from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import rpy2.robjects as robjects
import yaml
from rpy2.robjects import default_converter, pandas2ri
from rpy2.robjects.conversion import localconverter
from rpy2.robjects.packages import importr

from pipeline.ingest.context import IngestContext
from pipeline.paths import DEFAULT_PATHS, UniversePaths

_MESH_CHUNK_SIZE = 500
_SELECT_COLUMNS = ("GENEID", "MESHID", "MESHCATEGORY", "SOURCEDB", "SOURCEID")


def _ensure_r_home() -> None:
    if "R_HOME" not in os.environ:
        os.environ["R_HOME"] = subprocess.check_output(
            ["R", "RHOME"], text=True
        ).strip()


def _load_r_packages() -> None:
    _ensure_r_home()
    importr("AnnotationHub")
    importr("MeSHDbi")


def load_source_metadata(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_descriptor_uis_from_staging(records_path: Path) -> frozenset[str]:
    """Descriptor UIs from nih-mesh staging records (row_kind=descriptor)."""
    uis: set[str] = set()
    with records_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("row_kind") != "descriptor":
                continue
            ui = record.get("descriptor_ui")
            if ui:
                uis.add(ui)
    return frozenset(uis)


def resolve_mesh_descriptor_staging(
    metadata: dict[str, Any],
    *,
    run_id: str,
    paths: UniversePaths = DEFAULT_PATHS,
) -> Path:
    filter_cfg = metadata.get("mesh_descriptor_filter") or {}
    source_name = filter_cfg.get("source_name", "nih-mesh")
    staging_run_id = filter_cfg.get("staging_run_id", run_id)
    return paths.staging_records(source_name, staging_run_id)


def open_mesh_db() -> robjects.RObject:
    """Load the latest Homo sapiens MeSHDb resource from AnnotationHub."""
    _load_r_packages()
    return robjects.r("""
    ah <- AnnotationHub()
    qr <- query(ah, c("MeSHDb", "Homo sapiens"))
    if (length(qr) == 0) {
        stop("No MeSHDb resource found for Homo sapiens in AnnotationHub")
    }
    # Prefer the newest hub record; fall back if cache/download is unreadable.
    idx_order <- order(as.integer(sub("^AH", "", names(qr))), decreasing = TRUE)
    mesh_db <- NULL
    for (idx in idx_order) {
        candidate <- MeSHDb(qr[[idx]])
        ok <- tryCatch({ columns(candidate); TRUE }, error = function(e) FALSE)
        if (ok) {
            mesh_db <- candidate
            break
        }
    }
    if (is.null(mesh_db)) {
        stop("No readable MeSHDb resource found in AnnotationHub")
    }
    mesh_db
    """)


def mesh_db_metadata(mesh_db: robjects.RObject) -> dict[str, list[str]]:
    _load_r_packages()
    robjects.globalenv["mesh_db"] = mesh_db
    return {
        "columns": list(robjects.r("columns(mesh_db)")),
        "keytypes": list(robjects.r("keytypes(mesh_db)")),
    }


def select_mesh_gene_mappings(
    mesh_db: robjects.RObject,
    mesh_ids: Sequence[str],
    columns: tuple[str, ...] = _SELECT_COLUMNS,
) -> Any:
    """Return gene→MeSH mappings for the given MeSH descriptor IDs."""
    _load_r_packages()
    if not mesh_ids:
        return pd.DataFrame(columns=list(columns))

    select = robjects.r["select"]
    mesh_id_list = tuple(sorted(set(mesh_ids)))
    frames: list[Any] = []

    for start in range(0, len(mesh_id_list), _MESH_CHUNK_SIZE):
        chunk = mesh_id_list[start : start + _MESH_CHUNK_SIZE]
        result = select(
            mesh_db,
            keys=robjects.StrVector(chunk),
            columns=robjects.StrVector(columns),
            keytype="MESHID",
        )
        with localconverter(default_converter + pandas2ri.converter):
            frames.append(robjects.conversion.rpy2py(result))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=list(columns))


def iter_gene_mesh_rows(
    allowed_mesh_ids: frozenset[str],
    mesh_db: robjects.RObject | None = None,
) -> Iterator[dict[str, str]]:
    """Yield gene→MeSH rows for MeSH IDs present in the allowlist."""
    if not allowed_mesh_ids:
        return

    db = mesh_db or open_mesh_db()
    df = select_mesh_gene_mappings(db, allowed_mesh_ids)
    for _, row in df.iterrows():
        mesh_id = str(row["MESHID"])
        if mesh_id not in allowed_mesh_ids:
            continue
        yield {
            "GENEID": str(row["GENEID"]),
            "MESHID": mesh_id,
        }


def iter_gene_mesh_rows_for_ingest(
    source_metadata_path: Path,
    *,
    ctx: IngestContext,
    mesh_db: robjects.RObject | None = None,
) -> Iterator[dict[str, str]]:
    metadata = load_source_metadata(source_metadata_path)
    staging_path = resolve_mesh_descriptor_staging(
        metadata,
        run_id=ctx.run_id,
        paths=ctx.paths,
    )
    if not staging_path.exists():
        filter_cfg = metadata.get("mesh_descriptor_filter") or {}
        source_name = filter_cfg.get("source_name", "nih-mesh")
        raise FileNotFoundError(
            f"{source_name} staging records required before bioconductor-meshdbi: "
            f"{staging_path}"
        )

    allowed_mesh_ids = load_descriptor_uis_from_staging(staging_path)
    yield from iter_gene_mesh_rows(allowed_mesh_ids, mesh_db=mesh_db)
