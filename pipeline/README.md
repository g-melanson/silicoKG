# silicoKG pipeline

Runtime artifacts live under `universe/{run_id}/` using the layout in `pipeline/paths.py`.

## Tiers

| Tier | Path | Artifact |
|------|------|----------|
| 1-staging | `universe/{run_id}/1-staging/{source}/` | `records.jsonl`, `manifest.json` |
| 2-bronze | `universe/{run_id}/2-bronze/{source}/` | `records.jsonl`, `quarantine.jsonl` |
| 3-silver | `universe/{run_id}/3-silver/{source}/` | `fragments.jsonl`, `quarantine.jsonl` |
| 4-merged | `universe/{run_id}/4-merged/` | `nodes.jsonl`, `edges.jsonl`, `resolution_report.json` |
| 5-gold | `universe/{run_id}/5-gold/` | `nodes.jsonl`, `edges.jsonl`, `quarantine/` |

HTTP fetch cache: `universe/cache/{source}/`

## Stage scope

| Stage | Scope | CLI |
|-------|-------|-----|
| ingest | per source | `python -m pipeline.ingest.cli` |
| validate | per source | `python -m pipeline.validate.cli` |
| transform | per source | `python -m pipeline.transform.cli` |
| integrate | **run-level** (all sources) | `python -m pipeline.integrate.cli` |
| publish | **run-level** | `python -m pipeline.publish.cli` |

Integrate reads every selected `3-silver/{source}/fragments.jsonl` under the same `run_id` and writes a single `4-merged/` directory. It is not invoked once per source.

## Neo4j export

After publish, export gold tier to Neo4j bulk-import CSV. Rules can be declared in the run YAML:

```yaml
export_neo4j:
  stub_nodes: false
```

When run via `pipeline.run`, `exclude_edge_types` inherits from the `publish` block or gold manifest.
Use `exclude_node_properties` only when gold nodes still include those fields.

Run as a pipeline stage (`export_neo4j`) or standalone:

```bash
python -m pipeline.export.neo4j.cli --run-id test-x --run-config pipeline/run/examples/ncbi-gene-info-summary.yaml
```

Writes `universe/{run_id}/5-gold/export/neo4j/nodes/{Label}.csv`, `relationships.csv`, and `manifest.json`.

## Neo4j load

### Bulk import (recommended)

Use `neo4j-admin database import full` for large datasets. **Neo4j must be stopped** before import.

```bash
python -m pipeline.load.neo4j.cli \
  --admin \
  --run-id test-x \
  --overwrite
```

Or point at the export manifest directly:

```bash
python -m pipeline.load.neo4j.cli \
  --admin \
  --manifest universe/test-x/5-gold/export/neo4j/manifest.json \
  --overwrite
```

Preview the command without running it:

```bash
python -m pipeline.load.neo4j.cli --admin --run-id test-x --dry-run
```

Set `NEO4J_HOME` or `NEO4J_ADMIN` if `neo4j-admin` is not on `PATH`. For Docker Neo4j, run the printed command inside the container with CSV paths mounted into the container filesystem.

### Live Bolt load

Load exported CSV into a running Neo4j instance over Bolt (slower; requires `pip install neo4j`):

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_PASSWORD=your-password

python -m pipeline.load.neo4j.cli \
  --manifest universe/test-x/5-gold/export/neo4j/manifest.json
```

Or pass paths directly:

```bash
python -m pipeline.load.neo4j.cli \
  --nodes-dir universe/test-x/5-gold/export/neo4j/nodes \
  --relationships-csv universe/test-x/5-gold/export/neo4j/relationships.csv \
  --uri bolt://localhost:7687 \
  --password your-password
```

Use `--clear` to wipe the target database before Bolt loading. Progress bars are shown by default; pass `--no-progress` to disable them.

## Silver fragment envelope

Each `fragments.jsonl` line:

```json
{
  "class": "Gene",
  "object": { "id": "silkg:Gene:9606:1", "@type": "Gene", ... },
  "source": {
    "source_name": "ncbi-gene-info",
    "silver_run_id": "...",
    "bronze_line": 0,
    "gene_id": "1",
    "tax_id": "9606"
  }
}
```

See `docs/plans/identity-contract.md` for URI formulas and merge rules.

## Identity registries

| File | Role |
|------|------|
| `schemas/prefixes.yaml` | CURIE prefix map |
| `schemas/enums/edge-predicates.yaml` | Edge class → predicate CURIE |
| `schemas/integrate-priorities.yaml` | Source rank + slot overrides for merge |

## Orchestration

Multi-stage runs use `python -m pipeline.run.cli` with a YAML context (`pipeline/run/examples/`). Per-source stages run for each source; integrate and publish run once per run id after transforms complete.
