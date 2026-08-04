# Pipeline run (YAML orchestration)

Execute a pipeline from a YAML **run context** instance. Individual stages keep
their own CLIs; this package only loads arguments and forwards them to each
stage's `run()`.

## Run

```bash
# from repo root
PYTHONPATH=. python -m pipeline.run.cli pipeline/run/examples/ncbi-gene-info.yaml
# or
PYTHONPATH=. python -m pipeline.run pipeline/run/examples/ncbi-gene-info.yaml
```

Single-stage CLIs are unchanged, e.g.:

```bash
PYTHONPATH=. python -m pipeline.ingest.cli --source ncbi --source-name ncbi-gene-info
```

## YAML shape

| Field | Required | Notes |
| --- | --- | --- |
| `sources` | yes | Non-empty list; each item needs `source` and `source_name` |
| `stages` | no | Defaults to `[ingest]`; known: ingest, validate, transform, integrate, publish, export_neo4j |
| `run_id` | no | UTC timestamp if omitted |
| `snapshot_raw` | no | Top-level ingest flag |
| `verbose` | no | Logging |
| `<stage>` | no | Optional dict of stage-specific args (`publish`, `export_neo4j`, `transform`, …) |

Transform tuning:

```yaml
transform:
  parallel_sources: false  # ProcessPool over sources when true
  workers: 1               # Intra-source bronze sharding per source
  limit: null              # Cap bronze rows (dev)
```

Example projection and export rules:

```yaml
publish:
  exclude_edge_types: [GeneHasDbXref]

export_neo4j:
  stub_nodes: false
```

`publish.strip_slots` merges with defaults (`sources`, `alternates`, `dbxrefs`, `same_as`).
`export_neo4j.exclude_edge_types` inherits from `publish` or the gold manifest when omitted.
Use `export_neo4j.exclude_node_properties` only when exporting gold that still carries those fields.

See `examples/ncbi-gene-info-summary.yaml`.
