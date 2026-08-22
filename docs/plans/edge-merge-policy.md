# Execution plan: edge merge policy (first contribution wins)

Close the integrate review item **“Edge merge has no conflict resolution”** (`pipeline/integrate/merge.py`) without introducing node-style priority merge on edges.

**Status:** Implemented. Policy B is the contract in `apply_edge_contribution`, [identity-contract.md](./identity-contract.md) §5.3, and `resolution_report.json`.

**Decision: Policy B** — the first contribution that establishes an edge key owns the payload; later contributions append provenance only. Conflicting non-key values are not merged into `alternates`. They are tested, documented, and counted so they are never an accidental silent drop.

---

## Why this is not Option A

Nodes and edges are different merge problems.

| | Nodes | Edges |
|---|---|---|
| Identity | `(id, @type)` | `(@type, subject, predicate, object)` via `_edge_key` |
| Why multiple fragments? | Many sources describe the **same entity** with competing scalars (`symbol`, `description`) | Many fragments assert the **same typed triple** (often extra bronze lines of one source) |
| Conflict tool | `IntegratePriorities` + `alternates[]` | Not applicable: identity fields cannot disagree inside one bucket |
| What `apply_*_contribution` folds | Every non-reserved slot | Provenance only, after the first fragment |

Passing `IntegratePriorities` into `apply_edge_contribution` would invent a reconciliation stage the identity contract never defined. It would also paper over a real modelling choice: gene2refseq emits one `GenomicSequenceMapsGene` per `(contig, gene)` while bronze is per transcript/protein row. Collapsing those rows is the point of the edge key, not a bug to priority-merge away.

---

## What the review got wrong

The reviewer’s example treats `start` / `end` as relationship endpoints:

```text
source_a:  start=gene:123  end=pathway:456
source_b:  start=gene:999  end=pathway:456
→ second start silently discarded
```

That cannot happen in this pipeline.

1. Edges use `subject` / `object`, not Neo4j `:START_ID` / `:END_ID`, at merge time.
2. `_edge_key` in `pipeline/integrate/engine.py` is:

   ```text
   (@type, subject, predicate, object)
   ```

   Different `subject` values are **two edges**, not two contributions to one edge. `apply_edge_contribution` is never called with conflicting endpoints.

3. In this repo, `start` / `end` are **genomic coordinates** on `GenomicSequenceMapsGene` (see `ncbi-gene2refseq.transform.yaml`). They are payload, not identity.

The `_obj` unused after the first contribution **is** real. The thing it can drop is payload (`start`, `end`, `map_location`, `orientation`, `status`, `id`, …), not the endpoints.

---

## What the “canonicalized nodes” framing got slightly wrong

Integrate is **one pass** over silver. Nodes are not canonicalized first and then have edges hung on them. Transform already minted URIs. A later contribution in `apply_edge_contribution` is another assertion of the **same 4-tuple**, usually from more bronze lines of the same source.

The production pattern is already in the small fixture:

```text
silkg:GenomicSequenceMapsGene:9606:NC_000008.11:9
  subject/object/predicate identical
  start=18170466  end=18223688     ← first bronze line
  sources[] = bronze_line 14, 15, 16, 17, 18
```

Five gene2refseq rows collapsed onto one gene-level `MAPS_TO` edge. That is expected. First line in **stream order** (source list × file order) owns coordinates. `IntegratePriorities` is not consulted.

A test that reuses the same `subject`/`object` on both contributions does **not** prove first-wins. It only proves identity preservation. The review asked for a second contribution with **different** payload.

---

## Policy

**Edge identity** is the 4-tuple. `object.id` is not used for dedup (already in §5.3).

**Edge payload** (everything except the 4-tuple and `sources[]`) is first-contribution-wins. “First” means stream order, not source rank. Later fragments:

- always append `{source_name, silver_run_id, bronze_line}` to `sources[]`;
- never overwrite canonical payload;
- if a later non-empty payload slot disagrees with the kept value, that disagreement is **counted** (and a small sample recorded). It is not written onto the edge as `alternates`.

Empty incoming values are not disagreements.

Quarantine is **not** used for payload disagreement. gene2refseq isoform collapse would fail every production run.

Implemented as `edge_payload_conflicts()` in `pipeline/integrate/merge.py`, counted on `IntegrateSummary`, written by `pipeline/integrate/runner.py` into `resolution_report.json` (`edge_payload_conflicts`, `edge_payload_conflict_samples`, cap 20).

---

## Design decisions

| Decision | Rationale |
|----------|-----------|
| Policy B, not A | Edge key already isolates identity; competing payload is duplicate-triple collapse, not multi-source entity merge |
| Do not pass `IntegratePriorities` into edge fold | Rank is a node-scalar tool; using it here implies a contract we are explicitly not taking |
| Do not put `alternates[]` on edges in this change | That is Option A-lite and would leak into publish/export |
| Document in code **and** `identity-contract.md` §5.3 | The review’s real complaint is undocumented first-wins, not missing priorities |
| Test conflicting **payload**, not conflicting endpoints | Endpoint conflict is a different code path (two keys → two edges) |
| Count payload disagreements; do not quarantine | Satisfies “never silently drop without trace” without breaking gene2refseq |
| Compare only non-empty, non-key slots | Avoid noise from missing optional coordinates |

---

## Phase 1 — Write the invariant where the next reader will look — done

**Why:** `_obj` in `source_name, _obj, source_meta = contribution` currently reads as accidental discard.

### 1.1 `apply_edge_contribution` / `merge_edge_fragments`

Docstrings state:

- this stage dedups typed triples, it does not reconcile source-specific edge attributes;
- the first contribution copies the object (`ensure_edge_predicate`);
- later contributions add provenance only;
- `start`/`end` on mapping edges are payload and follow first-wins;
- `subject`/`object` cannot conflict inside one call because they are the key.

`_obj` stays unused on the append path. Engine compares it via `edge_payload_conflicts` before the fold.

### 1.2 `docs/plans/identity-contract.md` §5.3

Payload policy is in §5.3: first contribution wins; later fragments provenance-only; stream order not rank; payload disagreements counted in `resolution_report.json`, not `alternates`. Links here for why not A.

---

## Phase 2 — Tests that actually lock the policy — done

**Why:** `test_fold_matches_batch_edge_merge` uses two identical TFLink fragments. That is necessary (fold ≡ batch) and insufficient (does not prove first-wins).

### 2.1 First payload wins, provenance unions

`test_first_edge_payload_wins_conflicting_coordinates` in `pipeline/integrate/tests/test_merge.py`.

### 2.2 Different subject ⇒ two edges (engine)

`test_integrate_different_subject_yields_two_edges` in `pipeline/integrate/tests/test_integrate_engine.py`.

### 2.3 Existing fold ≡ batch still passes

`test_fold_matches_batch_edge_merge` unchanged. Conflicts live on `IntegrateSummary`, not the merge dict.

---

## Phase 3 — Trace disagreements (do not merge them) — done

**Why:** A comment plus a unit test still drops real gene2refseq coordinate disagreements in production with no run-level signal. The review’s “never silently drop without trace” is about that.

### 3.1 Compare incoming payload to canonical

`edge_payload_conflicts()`:

- Ignore key slots: `@type`, `subject`, `predicate`, `object`.
- Ignore `sources`.
- Ignore empty incoming values.
- If canonical slot is non-empty and `!=` incoming, that is one disagreement.

`id` is payload for this purpose: it is not the dedup key; first `id` wins.

### 3.2 Record on `IntegrateSummary` / `resolution_report.json`

Do **not** put `alternates` on the edge. Shape:

```json
{
  "redirects": [],
  "merged_nodes": 0,
  "merged_edges": 0,
  "quarantined": 0,
  "edge_payload_conflicts": 0,
  "edge_payload_conflict_samples": [
    {
      "key": ["GenomicSequenceMapsGene", "silkg:GenomicSequence:9606:NC_…", "silkg:MAPS_TO", "silkg:Gene:9606:9"],
      "slot": "start",
      "kept": "18170466",
      "dropped": "…",
      "source_name": "ncbi-gene2refseq",
      "bronze_line": 15
    }
  ]
}
```

Sample cap is `EDGE_PAYLOAD_CONFLICT_SAMPLE_CAP` (20). Count can be large; the sample must not be. Non-zero count does not fail the run.

### 3.3 Test the counter

`test_edge_payload_conflicts_on_disagreement`, `test_edge_payload_conflicts_identical_is_quiet`, `test_integrate_counts_edge_payload_conflicts`.

---

## Out of scope

- Priority-aware edge scalars / `alternates` on edges (Option A). Revisit only if two **different sources** routinely assert the same 4-tuple with meaningful competing payload **and** product wants a winner other than stream order.
- Changing `_edge_key` to include `start`/`end` (that would split gene-level `MAPS_TO` into isoform-level edges).
- Gene-history redirect pre-pass (`identity-contract.md` §5.5).
- Publish/export of a new edge field.

---

## Suggested order of work

Phases 1–3 are done. Remaining work is out of scope (Option A, changing `_edge_key`, redirects).

---

## Success metrics

- [x] `identity-contract.md` §5.3 states first-contribution-wins + stream order + no edge `alternates`.
- [x] `apply_edge_contribution` docstring states the same invariant.
- [x] Test: same key, different `start`/`end` → first payload kept, two `sources`.
- [x] Test: different `subject` → two edges from `integrate_silver_paths`.
- [x] `pytest pipeline/integrate/tests/` passes.
- [x] (Phase 3) `resolution_report.json` has `edge_payload_conflicts` and a bounded sample list.
- [x] (Phase 3) Identical second payload does not increment the counter.
- [x] No call from `apply_edge_contribution` into `IntegratePriorities`.
