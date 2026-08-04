# Transform (bronze → silver)

Stream bronze JSONL through LinkML-Map class derivations into silver fragment envelopes.

## CLI

```bash
PYTHONPATH=. python -m pipeline.transform.cli \
  --source ncbi \
  --source-name ncbi-gene-info \
  --source-row-class NCBIGeneInfoRow \
  --bronze-run-id test-small \
  --run-id test-small \
  --workers 1 \
  --limit 100
```

| Flag | Default | Notes |
|------|---------|-------|
| `--workers N` | `1` | ProcessPool bronze line-range sharding; each worker builds its own transformer |
| `--limit N` | none | Cap bronze rows (dev / profiling) |
| `--bronze-run-id` | required | Bronze directory under `universe/{id}/2-bronze/` |

Orchestrator YAML (`pipeline/run`) also accepts:

```yaml
transform:
  parallel_sources: false  # ProcessPool over sources
  workers: 1               # forwarded to each source transform
  limit: null
```

## Profiling

```bash
PYTHONPATH=. python -m cProfile -o transform-gene2refseq.prof \
  -m pipeline.transform.cli --source ncbi --source-name ncbi-gene2refseq \
  --run-id test-x --bronze-run-id test-x --source-row-class NCBIGene2RefSeqRow
```

## Artifacts

- `universe/{run_id}/3-silver/{source_name}/fragments.jsonl`
- `quarantine.jsonl`, `manifest.json` (includes `duration_seconds`, `workers`)
