"""Optional tqdm progress bars for long-running pipeline loops."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Iterator
from contextvars import ContextVar
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

_progress_enabled: ContextVar[bool] = ContextVar("progress_enabled", default=False)
_configured: ContextVar[bool] = ContextVar("progress_configured", default=False)


def configure(*, enabled: bool | None = None) -> None:
    """Enable or disable progress bars for the current context."""
    _configured.set(True)
    if enabled is None:
        enabled = sys.stderr.isatty()
    _progress_enabled.set(enabled)


def is_enabled() -> bool:
    _ensure_default_configured()
    return _progress_enabled.get()


def _ensure_default_configured() -> None:
    if not _configured.get():
        configure()


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def track(
    iterable: Iterable[T],
    *,
    total: int | None = None,
    desc: str,
    unit: str = "it",
) -> Iterator[T]:
    """Wrap *iterable* with a tqdm bar when progress is enabled."""
    if not is_enabled():
        yield from iterable
        return

    from tqdm import tqdm

    yield from tqdm(iterable, total=total, desc=desc, unit=unit, file=sys.stderr)


def iter_file_lines(
    path: Path,
    *,
    desc: str,
    unit: str = "lines",
) -> Iterator[bytes]:
    """Iterate over a file's lines with an optional progress bar."""
    total = count_lines(path) if is_enabled() else None
    with path.open("rb") as handle:
        yield from track(handle, total=total, desc=desc, unit=unit)


def iter_indexed_jsonl(
    path: Path,
    *,
    desc: str,
    loads: Callable[[bytes | str], dict],
) -> Iterator[tuple[int, dict]]:
    """Yield ``(line_number, record)`` from a JSONL file with progress."""
    for line_number, line in enumerate(iter_file_lines(path, desc=desc)):
        if not line.strip():
            continue
        yield line_number, loads(line)


def write_message(message: str) -> None:
    """Print a status line without breaking active progress bars."""
    if is_enabled():
        from tqdm import tqdm

        tqdm.write(message, file=sys.stderr)
    else:
        print(message, file=sys.stderr)
