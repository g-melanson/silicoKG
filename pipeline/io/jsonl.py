"""Fast JSONL helpers backed by orjson."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO

import orjson


def loads_line(line: bytes | str) -> dict:
    """Parse one JSONL line into a dict."""
    if isinstance(line, str):
        line = line.encode("utf-8")
    return orjson.loads(line)


def dumps_line(obj: Any) -> bytes:
    """Serialize one object as a JSONL line (including trailing newline)."""
    return orjson.dumps(obj) + b"\n"


class JsonlWriter:
    """Buffered binary JSONL writer."""

    def __init__(
        self,
        path: Path,
        *,
        mode: str = "wb",
        buffer_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self._path = path
        self._mode = mode
        self._buffer_bytes = buffer_bytes
        self._file: BinaryIO | None = None
        self._buf: list[bytes] = []
        self._size = 0

    def __enter__(self) -> JsonlWriter:
        self._file = self._path.open(self._mode)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def write(self, obj: Any) -> None:
        line = dumps_line(obj)
        self._buf.append(line)
        self._size += len(line)
        if self._size >= self._buffer_bytes:
            self.flush()

    def writelines_objs(self, objs: Iterable[Any]) -> None:
        for obj in objs:
            self.write(obj)

    def flush(self) -> None:
        if not self._buf or self._file is None:
            return
        self._file.writelines(self._buf)
        self._buf.clear()
        self._size = 0

    def close(self) -> None:
        self.flush()
        if self._file is not None:
            self._file.close()
            self._file = None
