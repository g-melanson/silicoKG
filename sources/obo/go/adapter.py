from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import yaml
from linkml_runtime.dumpers import json_dumper

from pipeline.ontology.context import OntologyContext
from pipeline.ontology.engine import iter_ontology_terms
from pipeline.ontology.load import load_owl
from pipeline.paths import REPO_ROOT
from sources.base import BaseAdapter
from sources.registry import register

_ONTOLOGY_CONFIG = REPO_ROOT / "pipeline/ontology/config.yaml"


def _go_context() -> OntologyContext:
    with _ONTOLOGY_CONFIG.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)["obo-go"]
    return OntologyContext(
        url=config["url"],
        source=config["source"],
        source_name=config["source_name"],
        ontology_namespace=config["ontology_namespace"],
        term_id_prefix=config["term_id_prefix"],
    )


def _row_to_dict(row: object) -> dict:
    data = json.loads(json_dumper.dumps(row))
    data.pop("@type", None)
    return data


@register
class GeneOntologyPlusAdapter(BaseAdapter):
    source = "obo-go"
    target_class = "GOTermRow"
    schema_path = Path(__file__).with_name("obo-go.schema.yaml")
    ingest_required_fields = ()

    def target_class_for_record(self, record: dict) -> str:
        if record.get("row_kind") == "edge":
            return "GOEdgeRow"
        return "GOTermRow"

    def parse(
        self,
        path: Path,
        *,
        ctx: IngestContext | None = None,
    ) -> Iterator[dict]:
        ctx: OntologyContext = _go_context()
        graph = load_owl(path)
        for row in iter_ontology_terms(graph, ctx):
            yield _row_to_dict(row)
