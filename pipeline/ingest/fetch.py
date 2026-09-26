"""Download publisher raw files into universe/cache with TTL."""

from __future__ import annotations

import gzip
import json
import logging
import shutil
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

CACHE_MANIFEST = "manifest.json"
# purl.obolibrary.org (Cloudflare) rejects urllib's default User-Agent with 403.
_USER_AGENT = "silicoKG/0.1 (ontology ingest)"


def _is_fresh(path: Path, ttl_seconds: int) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    age = datetime.now(UTC).timestamp() - path.stat().st_mtime
    return age < ttl_seconds

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
)
def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("downloading %s -> %s", url, dest)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)

    except urllib.error.URLError as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"download failed for {url!r}: {exc}") from exc

    tmp.replace(dest)


def _decompress_gzip(gz_path: Path, out_path: Path) -> None:
    log.info("decompressing %s -> %s", gz_path, out_path)
    tmp = out_path.with_suffix(out_path.suffix + ".part")
    with gzip.open(gz_path, "rb") as src, tmp.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    tmp.replace(out_path)


def _write_cache_manifest(cache_dir: Path, *, url: str, artifact: Path) -> None:
    manifest = {
        "url": url,
        "artifact": artifact.name,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    (cache_dir / CACHE_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_cached_download(
    url: str,
    cache_dir: Path,
    raw_filename: str,
    *,
    ttl_seconds: int = 21600,
    decompress: bool = True,
) -> Path:
    """Return a local path to a cached, parse-ready publisher file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact = cache_dir / raw_filename

    if _is_fresh(artifact, ttl_seconds):
        log.info("using cached artifact %s", artifact)
        return artifact

    if url.endswith(".gz"):
        gz_name = Path(url).name
        gz_path = cache_dir / gz_name
        if not _is_fresh(gz_path, ttl_seconds):
            _download(url, gz_path)
        if decompress:
            _decompress_gzip(gz_path, artifact)
            _write_cache_manifest(cache_dir, url=url, artifact=artifact)
            return artifact
        artifact = gz_path
    else:
        _download(url, artifact)

    _write_cache_manifest(cache_dir, url=url, artifact=artifact)
    return artifact
