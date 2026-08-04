"""Load OWL/RDF ontology files into an rdflib Graph."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from rdflib import Graph
from rdflib.util import guess_format

from pipeline.paths import REPO_ROOT

_URL_SCHEMES = frozenset({"http", "https", "ftp", "file"})


def _resolve_source(source: Path | str) -> Path | str:
    source_str = str(source)
    if source_str.startswith("local://"):
        return REPO_ROOT / source_str.removeprefix("local://")
    return source


def _is_url(source: str) -> bool:
    return urlparse(source).scheme in _URL_SCHEMES


def _resolve_format(source: str, *, format: str | None) -> str:
    if format is not None:
        return format

    guess_from = urlparse(source).path if _is_url(source) else source
    rdf_format = guess_format(fpath=guess_from)
    if rdf_format is None:
        raise ValueError(
            f"could not infer RDF format for {source!r}; pass format= explicitly"
        )
    return rdf_format


def load_owl(source: Path | str, *, format: str | None = None) -> Graph:
    """Parse an OWL or RDF source and return its triples as an rdflib Graph.

    ``source`` may be a local file path or an ``http(s)://`` URL. When
    ``format`` is omitted, rdflib infers the parser from the file extension
    (``.owl`` → RDF/XML, ``.ttl`` → Turtle, etc.).
    """
    resolved = _resolve_source(source)
    source_str = str(resolved)

    if _is_url(source_str):
        rdf_format = _resolve_format(source_str, format=format)
        graph = Graph()
        graph.parse(source_str, format=rdf_format)
        return graph

    owl_path = Path(resolved)
    if not owl_path.is_file():
        raise FileNotFoundError(f"OWL file not found: {owl_path}")

    rdf_format = _resolve_format(str(owl_path), format=format)
    graph = Graph()
    graph.parse(str(owl_path), format=rdf_format)
    return graph
