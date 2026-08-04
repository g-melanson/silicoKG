from pathlib import Path
from dataclasses import dataclass
from pipeline.paths import REPO_ROOT


@dataclass(frozen=True)
class OntologyPaths:

    def get_ontology_dir(self)->Path:
        return REPO_ROOT / "pipeline" / "ontology" 

    def get_sources_dir(self)->Path:
        return self.get_ontology_dir() / "sources"

    def get_source_dir(self, source: str)->Path:
        return self.get_sources_dir() / source

    def get_source_path(self, source: str, source_name: str)->Path:
        return self.get_source_dir(source) / source_name

    def get_source_file_schema_path(self, source: str, source_name: str)->Path:
        return self.get_source_path(source, source_name) / f"{source_name}.schema.yaml"

    def get_source_file_index_path(self, source: str, source_name: str)->Path:
        return self.get_source_path(source, source_name) / f"{source_name}.index.yaml"

DEFAULT_ONTOLOGY_PATHS = OntologyPaths()
