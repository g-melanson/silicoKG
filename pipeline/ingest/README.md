# Ingest tier

Parse publisher snapshots into `universe/{run_id}/1-staging/{source}/`.

## NCBI Gene Info

```bash
# from repo root
PYTHONPATH=. python -m pipeline.ingest.cli \
  --source ncbi \
  --source-name ncbi-gene-info \
  --snapshot-raw \
  -v
```

Config: `pipeline/ingest/config.yaml` (`url`, `ttl_seconds`, `raw_filename`, …).

Remote `http://`, `https://`, and `ftp://` URLs are downloaded into
`universe/cache/{source_name}/` and reused until `ttl_seconds` expires.
Gzip (`.gz`) URLs are decompressed to `raw_filename` in the cache.
Schema / column map: `sources/ncbi/ncbi_gene_info/ncbi-gene-info.schema.yaml`.

Outputs per run:

- `records.jsonl` — normalized rows
- `manifest.json` — run stats
- `raw/` — optional raw snapshot copy
- `rejects.jsonl` — only when rows fail validation
