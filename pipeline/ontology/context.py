from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.ontology.paths import DEFAULT_ONTOLOGY_PATHS, OntologyPaths


@dataclass(frozen=True)
class OntologyContext:
    url: str
    source: str
    source_name: str
    ontology_namespace: str
    term_id_prefix: str
    property_namespace: str | None = None
    property_id_prefix: str | None = None
    terms: tuple[str, ...] | None = None
    paths: OntologyPaths = DEFAULT_ONTOLOGY_PATHS

    def schema_path(self) -> Path:
        return self.paths.get_source_file_schema_path(self.source, self.source_name)
