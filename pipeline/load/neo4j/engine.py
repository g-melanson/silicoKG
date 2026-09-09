"""Parse Neo4j bulk-import CSV and load it via Bolt."""

from __future__ import annotations

import csv
import logging
import re
from tqdm import tqdm
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, TypeVar

from pipeline.export.neo4j.config import ARRAY_DELIMITER

log = logging.getLogger(__name__)

T = TypeVar("T")

LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RELATIONSHIP_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type_hint: str | None = None


@dataclass(frozen=True)
class NodeBatch:
    label: str
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class RelationshipBatch:
    rel_type: str
    rows: tuple[dict[str, Any], ...]


@dataclass
class Neo4jLoadSummary:
    node_count: int = 0
    node_count_by_label: dict[str, int] = field(default_factory=dict)
    relationship_count: int = 0
    relationship_count_by_type: dict[str, int] = field(default_factory=dict)


def parse_column_header(header: str) -> ColumnSpec:
    if header.startswith(":"):
        return ColumnSpec(name=header[1:], type_hint="reserved")
    if ":" in header:
        name, type_hint = header.rsplit(":", 1)
        return ColumnSpec(name=name, type_hint=type_hint)
    return ColumnSpec(name=header)


def _validate_label(label: str) -> str:
    if not LABEL_PATTERN.match(label):
        raise ValueError(f"invalid Neo4j label: {label!r}")
    return label


def _validate_relationship_type(rel_type: str) -> str:
    if not RELATIONSHIP_TYPE_PATTERN.match(rel_type):
        raise ValueError(f"invalid Neo4j relationship type: {rel_type!r}")
    return rel_type


def _coerce_cell(value: str, type_hint: str | None, *, array_delimiter: str) -> Any:
    if value == "":
        return None
    if type_hint == "string[]":
        return [item for item in value.split(array_delimiter) if item]
    return value


def _iter_csv_rows(path: Path) -> Iterator[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if row:
                yield row


def count_csv_data_rows(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _progress_iter(
    iterable: Iterable[T],
    *,
    total: int | None,
    desc: str,
    show_progress: bool,
    unit: str = "row",
) -> Iterator[T]:
    if not show_progress:
        yield from iterable
        return
    yield from tqdm(iterable, total=total, desc=desc, unit=unit)


def parse_node_csv(
    path: Path,
    *,
    label: str | None = None,
    array_delimiter: str = ARRAY_DELIMITER,
    show_progress: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    row_iter = iter(_iter_csv_rows(path))
    try:
        header_row = next(row_iter)
    except StopIteration as exc:
        raise ValueError(f"node CSV is empty: {path}") from exc

    resolved_label = _validate_label(label or path.stem)
    columns = [parse_column_header(header) for header in header_row]
    if not columns or columns[0].name != "nodeId":
        raise ValueError(f"node CSV must start with nodeId:ID column: {path}")

    total = count_csv_data_rows(path) if show_progress else None
    rows: list[dict[str, Any]] = []
    for raw_row in _progress_iter(
        row_iter,
        total=total,
        desc=f"Reading {resolved_label}",
        show_progress=show_progress,
    ):
        node_id = raw_row[0]
        if not node_id:
            continue

        properties: dict[str, Any] = {}
        for column, cell in zip(columns[1:], raw_row[1:], strict=False):
            value = _coerce_cell(cell, column.type_hint, array_delimiter=array_delimiter)
            if value is not None:
                properties[column.name] = value

        rows.append({"nodeId": node_id, "properties": properties})

    return resolved_label, rows


def parse_relationships_csv(
    path: Path,
    *,
    array_delimiter: str = ARRAY_DELIMITER,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    row_iter = iter(_iter_csv_rows(path))
    try:
        header_row = next(row_iter)
    except StopIteration as exc:
        raise ValueError(f"relationship CSV is empty: {path}") from exc

    columns = [parse_column_header(header) for header in header_row]
    column_names = [column.name for column in columns]
    if column_names[:3] != ["START_ID", "END_ID", "TYPE"]:
        raise ValueError(
            "relationship CSV must start with :START_ID,:END_ID,:TYPE columns"
        )

    property_columns = columns[3:]
    total = count_csv_data_rows(path) if show_progress else None
    rows: list[dict[str, Any]] = []
    for raw_row in _progress_iter(
        row_iter,
        total=total,
        desc="Reading relationships",
        show_progress=show_progress,
    ):
        if len(raw_row) < 3:
            continue
        start_id, end_id, rel_type = raw_row[0], raw_row[1], raw_row[2]
        if not start_id or not end_id or not rel_type:
            continue

        properties: dict[str, Any] = {}
        for column, cell in zip(property_columns, raw_row[3:], strict=False):
            value = _coerce_cell(cell, column.type_hint, array_delimiter=array_delimiter)
            if value is not None:
                properties[column.name] = value

        rows.append(
            {
                "startId": start_id,
                "endId": end_id,
                "type": _validate_relationship_type(rel_type),
                "properties": properties,
            }
        )

    return rows


def discover_node_csvs(nodes_dir: Path) -> dict[str, Path]:
    if not nodes_dir.is_dir():
        raise FileNotFoundError(f"nodes directory not found: {nodes_dir}")

    node_files = sorted(nodes_dir.glob("*.csv"))
    if not node_files:
        raise FileNotFoundError(f"no node CSV files found in: {nodes_dir}")

    return {_validate_label(path.stem): path for path in node_files}


def group_relationships_by_type(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["type"]].append(row)
    return dict(grouped)


def group_relationships_by_endpoint_labels(
    rows: list[dict[str, Any]],
) -> dict[tuple[str | None, str | None], list[dict[str, Any]]]:
    grouped: dict[tuple[str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (infer_node_label(row["startId"]), infer_node_label(row["endId"]))
        grouped[key].append(row)
    return dict(grouped)


def chunk_rows(rows: list[dict[str, Any]], batch_size: int) -> Iterator[tuple[dict[str, Any], ...]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    for start in range(0, len(rows), batch_size):
        yield tuple(rows[start : start + batch_size])


def clear_database(session: Any) -> None:
    session.run("MATCH (n) DETACH DELETE n").consume()


def ensure_node_index(session: Any, label: str) -> None:
    _validate_label(label)
    session.run(
        f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.nodeId)"
    ).consume()


def ensure_relationship_endpoint_indexes(
    session: Any,
    *,
    node_files: dict[str, Path],
    relationships_by_type: dict[str, list[dict[str, Any]]],
) -> None:
    """Create label-scoped nodeId indexes for relationship MATCH endpoints."""
    labels: set[str] = set(node_files)
    for rows in relationships_by_type.values():
        for row in rows:
            for key in ("startId", "endId"):
                label = infer_node_label(row[key])
                if label:
                    labels.add(label)
    for label in sorted(labels):
        ensure_node_index(session, label)


def infer_node_label(node_id: str) -> str | None:
    """Infer a Neo4j label from a silkg canonical node id (silkg:Class:...)."""
    if not node_id.startswith("silkg:"):
        return None
    class_name = node_id[len("silkg:") :].split(":", 1)[0]
    if LABEL_PATTERN.match(class_name):
        return class_name
    return None


def load_node_batch(session: Any, label: str, rows: tuple[dict[str, Any], ...]) -> int:
    if not rows:
        return 0

    _validate_label(label)
    query = (
        f"UNWIND $rows AS row "
        f"MERGE (n:{label} {{nodeId: row.nodeId}}) "
        f"SET n += row.properties"
    )
    session.run(query, rows=list(rows)).consume()
    return len(rows)


def _node_match_clause(variable: str, id_field: str, label: str | None) -> str:
    if label:
        _validate_label(label)
        return f"MATCH ({variable}:{label} {{nodeId: row.{id_field}}}) "
    return f"MATCH ({variable} {{nodeId: row.{id_field}}}) "


def _merge_relationship_group(
    session: Any,
    rel_type: str,
    start_label: str | None,
    end_label: str | None,
    rows: list[dict[str, Any]],
) -> int:
    query = (
        f"UNWIND $rows AS row "
        f"{_node_match_clause('start', 'startId', start_label)}"
        f"{_node_match_clause('end', 'endId', end_label)}"
        f"MERGE (start)-[rel:{rel_type}]->(end) "
        f"SET rel += row.properties "
        f"RETURN count(*) AS written"
    )
    record = session.run(query, rows=rows).single()
    written = int(record["written"]) if record else 0
    skipped = len(rows) - written
    if skipped:
        log.warning(
            "skipped %s %s relationship(s); MATCH wrote %s of %s rows "
            "(start_label=%s end_label=%s)",
            skipped,
            rel_type,
            written,
            len(rows),
            start_label,
            end_label,
        )
    return written


def load_relationship_batch(
    session: Any,
    rel_type: str,
    rows: tuple[dict[str, Any], ...],
) -> int:
    if not rows:
        return 0

    rel_type = _validate_relationship_type(rel_type)
    written = 0
    grouped = group_relationships_by_endpoint_labels(list(rows))
    for (start_label, end_label), group_rows in sorted(
        grouped.items(),
        key=lambda item: (item[0][0] or "", item[0][1] or ""),
    ):
        written += _merge_relationship_group(
            session, rel_type, start_label, end_label, group_rows
        )
    return written


def _load_batches_with_progress(
    session: Any,
    *,
    rows: list[dict[str, Any]],
    batch_size: int,
    desc: str,
    show_progress: bool,
    load_batch,
) -> int:
    loaded = 0
    progress = tqdm(
        total=len(rows),
        desc=desc,
        unit="row",
        disable=not show_progress,
    )
    try:
        for batch in chunk_rows(rows, batch_size):
            if show_progress:
                progress.refresh()
            loaded += load_batch(session, batch)
            progress.update(len(batch))
    finally:
        progress.close()
    return loaded


def load_csv_files(
    driver: Any,
    *,
    node_files: dict[str, Path],
    relationships_csv: Path,
    database: str = "neo4j",
    batch_size: int = 1000,
    clear: bool = False,
    array_delimiter: str = ARRAY_DELIMITER,
    show_progress: bool = True,
) -> Neo4jLoadSummary:
    if not relationships_csv.exists():
        raise FileNotFoundError(f"relationship CSV not found: {relationships_csv}")

    summary = Neo4jLoadSummary()
    relationship_rows = parse_relationships_csv(
        relationships_csv,
        array_delimiter=array_delimiter,
        show_progress=show_progress,
    )
    relationships_by_type = group_relationships_by_type(relationship_rows)

    with driver.session(database=database) as session:
        if clear:
            if show_progress:
                tqdm.write("Clearing database...")
            clear_database(session)

        for label, path in sorted(node_files.items()):
            parsed_label, rows = parse_node_csv(
                path,
                label=label,
                array_delimiter=array_delimiter,
                show_progress=show_progress,
            )
            ensure_node_index(session, parsed_label)
            loaded = _load_batches_with_progress(
                session,
                rows=rows,
                batch_size=batch_size,
                desc=f"Loading {parsed_label}",
                show_progress=show_progress,
                load_batch=lambda session, batch: load_node_batch(
                    session, parsed_label, batch
                ),
            )
            summary.node_count += loaded
            summary.node_count_by_label[parsed_label] = loaded

        if relationships_by_type:
            if show_progress:
                tqdm.write("Ensuring nodeId indexes for relationship load...")
            ensure_relationship_endpoint_indexes(
                session,
                node_files=node_files,
                relationships_by_type=relationships_by_type,
            )

        for rel_type, rows in sorted(relationships_by_type.items()):
            loaded = 0
            for (start_label, end_label), labeled_rows in sorted(
                group_relationships_by_endpoint_labels(rows).items(),
                key=lambda item: (item[0][0] or "", item[0][1] or ""),
            ):
                endpoint_desc = (
                    f"{start_label or '*'}->{end_label or '*'}"
                )
                loaded += _load_batches_with_progress(
                    session,
                    rows=labeled_rows,
                    batch_size=batch_size,
                    desc=f"Loading {rel_type} ({endpoint_desc})",
                    show_progress=show_progress,
                    load_batch=lambda session, batch, rel_type=rel_type: (
                        load_relationship_batch(session, rel_type, batch)
                    ),
                )
            summary.relationship_count += loaded
            summary.relationship_count_by_type[rel_type] = loaded

    return summary
