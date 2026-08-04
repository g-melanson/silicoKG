from __future__ import annotations

import gzip
import urllib.request
from pathlib import Path

from pipeline.ingest.fetch import _USER_AGENT, ensure_cached_download


def test_ensure_cached_download_local_file_url(tmp_path: Path):
    raw = tmp_path / "sample.tsv"
    raw.write_text("tax_id\tGeneID\n9606\t1\n", encoding="utf-8")

    url = raw.as_uri()
    cache_dir = tmp_path / "cache"
    out = ensure_cached_download(
        url,
        cache_dir,
        "sample.tsv",
        ttl_seconds=3600,
    )
    assert out == cache_dir / "sample.tsv"
    assert out.read_text(encoding="utf-8").startswith("tax_id")


def test_ensure_cached_download_gzip_roundtrip(tmp_path: Path, monkeypatch):
    gz_src = tmp_path / "input.gz"
    with gzip.open(gz_src, "wt", encoding="utf-8") as f:
        f.write("tax_id\tGeneID\n9606\t1\n")

    url = gz_src.as_uri()
    cache_dir = tmp_path / "cache"
    out = ensure_cached_download(
        url,
        cache_dir,
        "input.tsv",
        ttl_seconds=3600,
    )
    assert out.read_text(encoding="utf-8") == "tax_id\tGeneID\n9606\t1\n"


def test_download_sends_user_agent(tmp_path: Path, monkeypatch):
    captured: dict[str, list[str]] = {}

    class FakeResponse:
        def read(self, n: int = -1) -> bytes:
            return b"ok\n"

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: urllib.request.Request, timeout: int = 300) -> FakeResponse:
        captured["user_agent"] = req.get_header("User-agent")
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    from pipeline.ingest.fetch import _download

    dest = tmp_path / "sample.tsv"
    _download("http://example.com/sample.tsv", dest)
    assert dest.read_text(encoding="utf-8") == "ok\n"
    assert captured["user_agent"] == [_USER_AGENT]
