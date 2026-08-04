# Scratch notes — identity contract critical review

> Temporary working document. Decisions marked **DECIDED** are confirmed.
> Delete or archive after `identity-contract.md` is merged.

## Confirmed decisions (from user)

| # | Decision | Value |
|---|----------|-------|
| D1 | Gene canonical URI | `silkg:Gene:{tax_id}:{gene_id}` **DECIDED** |
| D2 | External db xrefs | Emit `GeneHasDbXref` edge fragments; predicate `silkg:SAME_AS` **DECIDED** |
| D3 | Integrate attribute conflicts | Priority table per source (not manifest order) **DECIDED** |

---

## Cross-cutting findings (pre-phase)

- Silver today is **flat JSON** (`runner.py` writes `outcome.record` directly), not the envelope `{class, object, source}` from prior plans.
- Transform emits **4 fragments/row** including `GeneAliasRecord` sharing `id` with `Gene` — integrate blocker.
- `pipeline/run/runner.py` runs every stage **per source**; integrate must be **run-scoped** (one merge across all silvers).
- Domain schema still uses `path-walker` prefix; transforms use `silkg` — drift unresolved.
- `pipeline/README.md` referenced by `paths.py` does not exist.
- LinkML-Map `class_derivations` emit **one object per derivation**; fan-out from `dbxrefs[]` → N `GeneHasDbXref` edges needs engine or post-step (not expressible as single derivation).

---

## Phase 0 — Contract artifacts

### Review

| Item | Assessment |
|------|------------|
| `schemas/prefixes.yaml` | Necessary but insufficient alone — must drive domain schema migration |
| `schemas/predicates.yaml` | Must include `silkg:SAME_AS`, `silkg:HAS_GENE`, etc. |
| `pipeline/README.md` | Required; should document tier layout + integrate run-scope |
| Contract golden tests | Good; anchor on A1BG (`9606:1`) |
| Gene URI with tax_id | **DECIDED** — all endpoint formulas must update atomically |

### Gaps / risks

- **R0.1** No `GeneHasDbXref` class in domain schema yet — add before Phase 1.
- **R0.2** `SAME_AS` semantics: document as "silicoKG cross-reference edge" (not OWL owl:sameAs expansion at merge). External nodes (HGNC, Ensembl) may exist only as edge objects until a future source materializes them.
- **R0.3** Priority table schema undefined — need `schemas/integrate-priorities.yaml` with source ranks + optional per-slot overrides.
- **R0.4** Orchestrator design flaw: integrate cannot live in per-source loop — flag for Phase 2.

### Phase 0 learnings → actions

- Add `GeneHasDbXref` to domain schema (reified triple, predicate default `silkg:SAME_AS`).
- Add `schemas/integrate-priorities.yaml` to Phase 0 deliverables.
- Document integrate as **run-level stage** in universe contract.
- Define dbxref normalization rules in contract (e.g. `HGNC:HGNC:5` → `HGNC:5`).

### Phase 0 decisions

| ID | Decision |
|----|----------|
| P0-1 | Canonical prefix for silicoKG-owned entities: `silkg:` |
| P0-2 | Edge predicate for db xrefs: `silkg:SAME_AS` (not `skos:exactMatch`) |
| P0-3 | Priority file is normative; manifest order is not used for attribute merge |
| P0-4 | Fan-out derivations (1 bronze row → N edges) are a **transform engine concern** — document in contract |

---

## Phase 1 — Fix ncbi-gene-info transform

### Review

| Item | Assessment |
|------|------------|
| URI scope update | Straightforward YAML expr change; must touch Gene, Chromosome, ChromosomeHasGene together |
| Remove GeneAliasRecord | Required; fold synonyms into `Gene.synonyms` (normalize in adapter or bronze) |
| Fragment envelope | Runner change required — not just transform YAML |
| GeneHasDbXref fan-out | **High complexity** — ~4 xrefs × 194k genes ≈ 780k additional fragments |
| Quarantine schema | Runner writes raw bronze on failure; doesn't match planned quarantine shape |

### Gaps / risks

- **R1.1** LinkML-Map cannot iterate `dbxrefs` into N edges declaratively — need `expand_dbxref_edges()` in engine or adapter post-step.
- **R1.2** Fragment count grows from ~775k to ~1.5M+ with dbxref edges — streaming already required; confirm manifest counts.
- **R1.3** `GeneHasDbXref.id` must be deterministic: `silkg:GeneHasDbXref:{tax_id}:{gene_id}:{normalized_xref}`.
- **R1.4** Invalid/unparseable dbxrefs → quarantine line, not silent drop.
- **R1.5** Re-materializing silver invalidates existing universe runs — document as breaking change.
- **R1.6** Transform CLI has duplicate parser definitions (`build_parser` unused); minor cleanup opportunity.

### Phase 1 learnings → actions

- Implement envelope in `runner.py` before URI migration (provenance needed for integrate).
- Add dbxref fan-out in `engine.py` after primary derivations (configurable per transform spec or hardcoded for gene-info v1).
- Normalize synonyms in bronze adapter (dedupe, drop nulls) to simplify Gene derivation.
- Update edge id formula: `silkg:ChromosomeHasGene:{tax_id}:{chromosome}:{gene_id}`.

### Phase 1 decisions

| ID | Decision |
|----|----------|
| P1-1 | Synonym normalization moves to ingest/adapter (bronze), not transform expr |
| P1-2 | Dbxref fan-out implemented in transform engine (Phase 1), not deferred |
| P1-3 | Keep `Gene.dbxrefs` attribute **and** emit `GeneHasDbXref` edges (attribute for query convenience, edges for graph) |
| P1-4 | Silver envelope is mandatory in Phase 1 output |

---

## Phase 2 — Integrate stage MVP

### Review

| Item | Assessment |
|------|------------|
| New `pipeline/integrate/` package | Correct approach; mirror validate/transform layout |
| Node merge by `(id, @type)` | Sound for consistent URI strategy |
| Priority table | **DECIDED** — implement as sorted merge, not first-seen |
| Run-scoped integrate | **Critical** — must read all `3-silver/*/fragments.jsonl` under run_id |
| Streaming merge | Required at scale; cannot load 1.5M+ fragments into dict without spill strategy |

### Gaps / risks

- **R2.1** Orchestrator `_run_integrate` today receives `SourceSpec` — signature must change to run-level (no per-source).
- **R2.2** Classify fragments: node types vs edge types — maintain allowlist (`Gene`, `Chromosome` vs `ChromosomeHasGene`, `GeneHasDbXref`).
- **R2.3** External xref targets (HGNC:5) as edge `object` — merged **edges** only; no node merge for external CURIEs unless a source emits them.
- **R2.4** Priority table needs **slot-level** overrides (e.g. `description` prefers gene-summary over gene-info).
- **R2.5** `alternates[]` structure on merged nodes must be specified.
- **R2.6** Single-source integrate (gene-info only) is valid MVP — ~194k genes + chromosomes + ~780k xref edges + location edges.

### Phase 2 learnings → actions

- Split `pipeline/run/runner.py` stages into `per_source` vs `run_level` sets.
- Priority merge algorithm: for each scalar slot, walk sources in priority order, take first non-empty; if lower-priority differs, append to `alternates`.
- Multivalued slots (`synonyms`, `dbxrefs`): union regardless of priority.
- Edge dedup key: `( @type, subject, predicate, object )` — ignore edge `id` for dedup.
- Write integrate manifest listing source silvers consumed + priority file hash.

### Phase 2 decisions

| ID | Decision |
|----|----------|
| P2-1 | Integrate CLI: `--run-id`, `--sources` (optional filter), `--priorities schemas/integrate-priorities.yaml` |
| P2-2 | Default source priority: `ncbi-gene-info` = 100 (authority for Gene) |
| P2-3 | Node fragments and edge fragments use same JSONL envelope |
| P2-4 | Phase 2 scope: single-source only; multi-source wiring in Phase 3 |

---

## Phase 3 — ncbi-gene2refseq

### Review

| Item | Assessment |
|------|------------|
| Shared key `(tax_id, gene_id)` | Present in schema — consistent Gene URI trivial |
| RefSeq URI authority | Use `RefSeq:{accession.version}` as-is from bronze |
| Adapter missing | Ingest work required, not just transform |
| Gene stub risk | gene2refseq rows may reference genes absent from gene-info in same run — acceptable per contract |

### Gaps / risks

- **R3.1** gene2refseq is **many rows per gene** — edge volume much larger than gene-info.
- **R3.2** Need new edge types: `GeneHasTranscript`, `TranscriptEncodesProtein` (or similar) — add to domain schema in Phase 3 prep.
- **R3.3** Multi-source integrate test is the real Phase 3 exit criteria, not just transform.
- **R3.4** RefSeq accessions are versioned — URI includes version; version bumps create new nodes (correct behavior).

### Phase 3 learnings → actions

- Phase 3 integrates gene-info + gene2refseq — first test of priority table across sources.
- gene2refseq priority likely lower than gene-info for Gene attributes (gene-info remains authority).
- Add slot overrides: Gene.name/symbol → gene-info; no gene2refseq scalar enrichment expected.

### Phase 3 decisions

| ID | Decision |
|----|----------|
| P3-1 | RefSeq entities use external `RefSeq:` prefix, not `silkg:` |
| P3-2 | gene2refseq transform never mints Gene attributes — edges only + optional Gene stub with id only |
| P3-3 | Multi-source integrate becomes Phase 3 exit gate |

---

## Phase 4 — gene-summary + gene-neighbours

### Review

| Item | Assessment |
|------|------------|
| gene-summary | Enriches Gene text fields — priority table must prefer summary for `description` |
| gene-neighbours | Symmetric edges between Gene URIs — endpoint consistency critical |
| Schemas exist | Adapters/transforms still needed |

### Gaps / risks

- **R4.1** Priority table must add slot override: `Gene.description` → `[ncbi-gene-summary, ncbi-gene-info]`.
- **R4.2** gene-neighbours may reference genes not in gene-info — stub genes acceptable.
- **R4.3** Neighbour edges need dedup policy for undirected pairs (A–B vs B–A) — define predicate direction or canonical ordering.

### Phase 4 decisions

| ID | Decision |
|----|----------|
| P4-1 | `Gene.description` priority: gene-summary (90) > gene-info (100) — **note: higher number = higher priority** |
| P4-2 | Neighbour edges: directed `silkg:GENOMIC_NEIGHBOR_OF` with subject/object as in source file |
| P4-3 | Slot-level overrides live in `integrate-priorities.yaml` under `slots.Gene.description` |

---

## Phase 5 — gene-history

### Review

| Item | Assessment |
|------|------------|
| Redirect discontinued → current GeneID | Resolver-adjacent; distinct from SAME_AS dbxref edges |
| Schema typo | `discontinue_date::` double colon in `ncbi-gene-history.schema.yaml` — fix before ingest |
| SAME_AS for history | Discontinued→current is **identity redirect**, not external xref — use separate mechanism |

### Gaps / risks

- **R5.1** Do not use `GeneHasDbXref` / `SAME_AS` for discontinued GeneIDs — use `GeneIdentityRedirect` or integrate redirect table.
- **R5.2** Redirect pre-pass must rewrite edge endpoints before edge merge.
- **R5.3** Emit redirect entries in `resolution_report.json`.

### Phase 5 decisions

| ID | Decision |
|----|----------|
| P5-1 | Discontinued GeneID mapping: integrate redirect table (not SAME_AS edges) |
| P5-2 | Optional silver `GeneIdentityRedirect` fragments as redirect table input |
| P5-3 | Fix gene-history schema typo in Phase 5 prep |

---

## Phase 6 — refseq-uniprot

### Review

| Item | Assessment |
|------|------------|
| Links RefSeq ↔ UniProt | Both external CURIE namespaces |
| Consistent with Phase 3 | RefSeq nodes may already exist from gene2refseq |

### Gaps / risks

- **R6.1** Use `GeneHasDbXref`-style or new `ProteinSameAs` edge with `silkg:SAME_AS` between `RefSeq:` and `UniProt:`?
- **R6.2** User chose SAME_AS for dbxref pattern — extend to cross-refseq-uniprot edges for consistency.

### Phase 6 decisions

| ID | Decision |
|----|----------|
| P6-1 | RefSeq↔UniProt edges use `@type: ProteinSameAs`, predicate `silkg:SAME_AS` |
| P6-2 | Validate gene-info dbxrefs against uniprot source as optional QA, not merge requirement |

---

## Phase 7 — Gold / publish

### Review

| Item | Assessment |
|------|------------|
| 5-gold projection | Optional validation + CURIE expansion |
| Neo4j/RDF export | Downstream; not blocking integrate |

### Gaps / risks

- **R7.1** Gold may collapse `alternates` for consumer simplicity — document projection rules.
- **R7.2** External xref nodes (HGNC, Ensembl) remain edge-only until dedicated sources added.

### Phase 7 decisions

| ID | Decision |
|----|----------|
| P7-1 | Gold preserves merged nodes/edges; quarantine split to `5-gold/quarantine/` |
| P7-2 | CURIE expansion optional via `schemas/prefixes.yaml` |

---

## Revised priority table (draft)

```yaml
# schemas/integrate-priorities.yaml (draft)
# Higher rank = wins for scalar slot conflicts
sources:
  ncbi-gene-info: 100
  ncbi-gene-summary: 90
  ncbi-gene2refseq: 50
  ncbi-gene-neighbours: 40
  ncbi-gene-group: 40
  ncbi-gene-history: 30
  ncbi-gene-refseq-to-uniprot: 20

slots:
  Gene:
    description: [ncbi-gene-summary, ncbi-gene-info]  # slot override order
    name: [ncbi-gene-info, ncbi-gene-summary]
    symbol: [ncbi-gene-info]
```

---

## Open items remaining

- [ ] Confirm P1-3: keep both `Gene.dbxrefs` attribute and SAME_AS edges (recommended yes).
- [ ] Neighbour edge dedup policy if source emits duplicates.
- [ ] Memory strategy for integrate at full NCBI scale (streaming + on-disk merge vs in-memory).

---

## Review complete

All 8 phases reviewed. Ready to write `identity-contract.md`.
