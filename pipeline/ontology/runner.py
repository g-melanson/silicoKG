"""Ontology index orchestration."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml
from rdflib import URIRef

from pipeline.config import parse_str_set
from pipeline.ontology.context import OntologyContext
from pipeline.ontology.engine import iter_ontology_terms
from pipeline.ontology.index import compile_index, write_index
from pipeline.ontology.load import load_owl
from pipeline.ontology.required_terms import collect_required_term_iris
from pipeline.paths import DEFAULT_PATHS, REPO_ROOT

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(source_name: str, config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or CONFIG_PATH
    if not path.is_absolute():
        path = REPO_ROOT / path
    with path.open(encoding="utf-8") as handle:
        all_config = yaml.safe_load(handle) or {}
    try:
        return all_config[source_name]
    except KeyError as exc:
        raise KeyError(f"no ontology config for source: {source_name}") from exc


def build_context(
    *,
    source: str,
    source_name: str,
    url: str,
    ontology_namespace: str,
    term_id_prefix: str,
    property_namespace: str | None = None,
    property_id_prefix: str | None = None,
    terms: frozenset[str] | None = None,
) -> OntologyContext:
    return OntologyContext(
        url=url,
        source=source,
        source_name=source_name,
        ontology_namespace=ontology_namespace,
        term_id_prefix=term_id_prefix,
        property_namespace=property_namespace,
        property_id_prefix=property_id_prefix,
        terms=tuple(sorted(terms)) if terms else None,
    )


def context_from_config(
    source_name: str,
    *,
    url: str | None = None,
    terms: frozenset[str] | None = None,
    config_path: Path | None = None,
) -> OntologyContext:
    config = load_config(source_name, config_path=config_path)
    configured_terms = parse_str_set(config.get("terms"), field="terms")
    merged_terms = terms or configured_terms
    return build_context(
        source=config["source"],
        source_name=config.get("source_name", source_name),
        url=url or config["url"],
        ontology_namespace=config["ontology_namespace"],
        term_id_prefix=config["term_id_prefix"],
        property_namespace=config.get("property_namespace"),
        property_id_prefix=config.get("property_id_prefix"),
        terms=merged_terms,
    )


def input_hash_for_graph(graph) -> str:
    serialized = graph.serialize(format="nt")
    if isinstance(serialized, bytes):
        payload = serialized
    else:
        payload = serialized.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def resolve_output_path(ctx: OntologyContext, output_path: Path | None = None) -> Path:
    if output_path is not None:
        return output_path
    return DEFAULT_PATHS.ontology_index_path(ctx.source_name)


def run(
    ctx: OntologyContext,
    *,
    output_path: Path | None = None,
) -> Path:
    """Load OWL, extract rows, compile index, and write output."""
    log.info("loading ontology from %s", ctx.url)
    graph = load_owl(ctx.url)

    term_refs = [URIRef(iri) for iri in ctx.terms] if ctx.terms else None
    rows = list(iter_ontology_terms(graph, ctx, term_refs))
    if not rows:
        raise RuntimeError("ontology extraction produced no rows")

    compiled = compile_index(
        rows,
        source_name=ctx.source_name,
        input_hash=input_hash_for_graph(graph),
    )
    destination = resolve_output_path(ctx, output_path=output_path)
    write_index(compiled, destination)

    log.info(
        "%s index written to %s (classes=%d restrictions=%d)",
        ctx.source_name,
        destination,
        compiled.stats.class_count,
        compiled.stats.restriction_count,
    )
    return destination


def run_named(
    source_name: str,
    *,
    url: str | None = None,
    terms: frozenset[str] | None = None,
    output_path: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    ctx = context_from_config(
        source_name,
        url=url,
        terms=terms,
        config_path=config_path,
    )
    return run(ctx, output_path=output_path)


def sync_index_from_rules(
    source_name: str,
    *,
    rules_path: Path,
    label_map_path: Path | None = None,
    output_path: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    """Rebuild a scoped index containing all SO classes referenced by rules/maps."""
    config = load_config(source_name, config_path=config_path)
    terms = collect_required_term_iris(
        rules_path=rules_path,
        label_map_path=label_map_path,
        ontology_namespace=config["ontology_namespace"],
        term_id_prefix=config["term_id_prefix"],
    )
    if not terms:
        raise RuntimeError("no SO class IRIs collected from rules/label map")
    return run_named(
        source_name,
        terms=terms,
        output_path=output_path,
        config_path=config_path,
    )
