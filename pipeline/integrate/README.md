# Integrate (silver → merged)

Merge silver fragment envelopes into priority-aware nodes and edges.
Source-specific ranking for a winning contributor is established in `schemas/integrate-priorities.yaml`

## CLI

```bash
PYTHONPATH=. python -m pipeline.integrate.cli \
  --run-id test-x \
  --sources ncbi-gene-info ncbi-gene-summary ncbi-gene-group ncbi-gene2refseq
```

## Profiling

```bash
PYTHONPATH=. python -m cProfile -o integrate.prof \
  -m pipeline.integrate.cli --run-id test-x \
  --sources ncbi-gene-info ncbi-gene-summary ncbi-gene-group ncbi-gene2refseq
```

## Artifacts

- `universe/{run_id}/4-merged/nodes.jsonl`
- `edges.jsonl`, `quarantine.jsonl`, `resolution_report.json`
- `manifest.json` (includes `duration_seconds`)

JSONL I/O uses `pipeline.io.jsonl` (orjson) with buffered writes.
