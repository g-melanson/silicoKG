"""Canonical runtime output paths under universe/.

Layout: universe/{run_id}/{tier}/{source}/…
Contract: pipeline/README.md (Universe output layout section)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

STAGING = "1-staging"
BRONZE = "2-bronze"
SILVER = "3-silver"
MERGED = "4-merged"
GOLD = "5-gold"
CACHE = "cache"
QUARANTINE = "quarantine"

RECORDS_JSONL = "records.jsonl"
FRAGMENTS_JSONL = "fragments.jsonl"
NODES_JSONL = "nodes.jsonl"
EDGES_JSONL = "edges.jsonl"
MANIFEST_JSON = "manifest.json"
REJECTS_JSONL = "rejects.jsonl"
DRIFT_REPORT_JSON = "drift_report.json"
RESOLUTION_REPORT_JSON = "resolution_report.json"
QUARANTINE_JSONL = "quarantine.jsonl"
RAW_DIR = "raw"
MAP_JSON = "map.json"
GOLD_QUARANTINE_DIR = "quarantine"
EXPORT = "export"
NEO4J = "neo4j"
NEO4J_NODES_DIR = "nodes"
NEO4J_RELATIONSHIPS_CSV = "relationships.csv"
NEO4J_MANIFEST_JSON = "manifest.json"
ONTOLOGY_INDEX_FILENAME = "index.yaml"
ONTOLOGY_MANIFEST_FILENAME = "ontology-manifest.json"

# source_name -> package dir under sources/{source}/ when it differs from
# the default source_name with hyphens replaced by underscores.
SOURCE_PACKAGE_DIRS: dict[str, str] = {
    "obo-go": "go",
    "uniprot-gaf": "gaf",
}


@dataclass(frozen=True, kw_only=True)
class UniversePaths:
    """All runtime pipeline output paths.

    Paths are grouped by pipeline ``run_id`` so one E2E run lives under
    ``universe/{run_id}/`` (staging, bronze, silver, merged, gold, quarantine).

    HTTP fetch cache stays shared at ``universe/cache/{source_name}/``.
    """

    root: Path = Path("universe")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "root",
            self.root if self.root.is_absolute() else REPO_ROOT / self.root,
        )

    def run_root(self, run_id: str) -> Path:
        return self.root / run_id

    def source_cache_dir(self, source_name: str) -> Path:
        """Shared HTTP fetch + compiled ontology artifacts for a source_name."""
        return self.root / CACHE / source_name

    def ontology_index_path(self, source_name: str) -> Path:
        return self.source_cache_dir(source_name) / ONTOLOGY_INDEX_FILENAME

    def ontology_manifest_path(self, source_name: str) -> Path:
        return self.source_cache_dir(source_name) / ONTOLOGY_MANIFEST_FILENAME

    def merged_nodes_pre_classify(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / "nodes.pre-classify.jsonl"

    def classify_manifest(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / "classify-manifest.json"

    def classify_quarantine_dir(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / QUARANTINE

    def classify_quarantine_nodes(self, run_id: str) -> Path:
        return self.classify_quarantine_dir(run_id) / NODES_JSONL

    # ── per-source tiers (under universe/{run_id}/) ──

    def staging_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / STAGING / source

    def bronze_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / BRONZE / source

    def silver_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / SILVER / source

    def merged_run_dir(self, run_id: str) -> Path:
        return self.run_root(run_id) / MERGED

    def gold_run_dir(self, run_id: str) -> Path:
        return self.run_root(run_id) / GOLD

    # ── file paths ──

    def staging_records(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / RECORDS_JSONL

    def staging_raw_dir(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / RAW_DIR

    def staging_manifest(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / MANIFEST_JSON

    def bronze_records(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / RECORDS_JSONL

    def bronze_manifest(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / MANIFEST_JSON

    def bronze_drift_report(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / DRIFT_REPORT_JSON

    def bronze_quarantine(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / QUARANTINE_JSONL

    def silver_fragments(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / FRAGMENTS_JSONL

    def silver_quarantine(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / QUARANTINE_JSONL

    def silver_manifest(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / MANIFEST_JSON

    def silver_map(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / MAP_JSON

    def merged_nodes(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / NODES_JSONL

    def merged_edges(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / EDGES_JSONL

    def merged_quarantine(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / QUARANTINE_JSONL

    def merged_resolution_report(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / RESOLUTION_REPORT_JSON

    def merged_manifest(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / MANIFEST_JSON

    def gold_nodes(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / NODES_JSONL

    def gold_edges(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / EDGES_JSONL

    def gold_manifest(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / MANIFEST_JSON

    def gold_quarantine_dir(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / GOLD_QUARANTINE_DIR

    def gold_quarantine_nodes(self, run_id: str) -> Path:
        return self.gold_quarantine_dir(run_id) / NODES_JSONL

    def gold_quarantine_edges(self, run_id: str) -> Path:
        return self.gold_quarantine_dir(run_id) / EDGES_JSONL

    def gold_export_neo4j_dir(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / EXPORT / NEO4J

    def gold_neo4j_nodes_dir(self, run_id: str) -> Path:
        return self.gold_export_neo4j_dir(run_id) / NEO4J_NODES_DIR

    def gold_neo4j_node_csv(self, run_id: str, label: str) -> Path:
        return self.gold_neo4j_nodes_dir(run_id) / f"{label}.csv"

    def gold_neo4j_relationships_csv(self, run_id: str) -> Path:
        return self.gold_export_neo4j_dir(run_id) / NEO4J_RELATIONSHIPS_CSV

    def gold_neo4j_manifest(self, run_id: str) -> Path:
        return self.gold_export_neo4j_dir(run_id) / NEO4J_MANIFEST_JSON

    @property
    def source_schema_path(self) -> Path:
        raise AttributeError(
            "Use source_schema_path_for(source, source_name) on UniversePaths"
        )

    @property
    def transform_schema_path(self) -> Path:
        raise AttributeError(
            "Use transform_schema_path_for(source, source_name) on UniversePaths"
        )

    def source_schema_path_for(self, source: str, source_name: str) -> Path:
        module_dir = _source_module_dir(source_name)
        return (
            REPO_ROOT
            / "sources"
            / source
            / module_dir
            / f"{source_name}.schema.yaml"
        )

    def transform_schema_path_for(self, source: str, source_name: str) -> Path:
        module_dir = _source_module_dir(source_name)
        return (
            REPO_ROOT
            / "sources"
            / source
            / module_dir
            / f"{source_name}.transform.yaml"
        )


def _source_module_dir(source_name: str) -> str:
    return SOURCE_PACKAGE_DIRS.get(source_name, source_name.replace("-", "_"))


DEFAULT_PATHS = UniversePaths()
