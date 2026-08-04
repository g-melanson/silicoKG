from dataclasses import dataclass

from pipeline.export.neo4j.config import Neo4jExportConfig
from pipeline.paths import DEFAULT_PATHS, UniversePaths


@dataclass
class Neo4jExportContext:
    run_id: str
    gold_run_id: str | None = None
    config: Neo4jExportConfig = Neo4jExportConfig()
    paths: UniversePaths = DEFAULT_PATHS

    @property
    def effective_gold_run_id(self) -> str:
        return self.gold_run_id or self.run_id
