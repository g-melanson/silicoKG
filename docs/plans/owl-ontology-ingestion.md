# OWL ontology ingestion — implementation guide

Ingest an OWL ontology file in full, compile a cached term index, and optionally annotate entity nodes via a **`classify`** stage (after integrate, before publish).

**First instance:** Sequence Ontology (`obo-so`, [so.owl](http://purl.obolibrary.org/obo/so.owl))  
**Related:** [`identity-contract.md`](./identity-contract.md), [`pipeline/README.md`](../../pipeline/README.md)

---

## What you are building

| Piece | What it is | Where it lives |
| --- | --- | --- |
| **Ontology index** | Full catalog of classes + extracted restrictions | `universe/cache/{source_name}/index.yaml` |
| **Bronze rows** | Every parsed class/restriction from one refresh run | `universe/{run_id}/2-bronze/{source_name}/records.jsonl` |
| **Classify stage** *(optional)* | Rule engine that writes ontology CURIEs onto entity nodes | mutates `universe/{run_id}/4-merged/nodes.jsonl` |
| **Entity slots** *(optional)* | e.g. `so_types`, `so_qualities` on `Gene` | merged → gold → Neo4j |

Ontology terms are **annotations** on entity nodes, not `@type`. Entity types (NCBI `Gene.type`, etc.) stay separate ([`identity-contract.md`](./identity-contract.md)).

This plan assumes **full-file ingestion**: every `owl:Class` in the ontology is extracted. There is no subset/BFS config.

---

## Two runs (do not merge them)

| Run | When | Commands | Output |
| --- | --- | --- | --- |
| **Ontology refresh** | When the OWL file changes | ingest → validate → **compile** | `universe/cache/{source_name}/index.yaml` |
| **Entity E2E** | Every entity pipeline run | ingest…integrate → **classify** → publish → export | ontology slots on matched entity nodes |

Entity runs **do not** re-ingest the OWL if `index.yaml` already exists. Classify only **reads** the cached index.

Ontology refresh **does not** go through transform, integrate, or publish.

---

## How it works

```
ONTOLOGY REFRESH (occasional, per source_name)
  {ontology}.owl ──ingest──► cache/{source_name}/{ontology}.owl
                 ──validate──► {run_id}/2-bronze/{source_name}/records.jsonl
                 ──compile──► cache/{source_name}/index.yaml

ENTITY E2E (every run — classify optional)
  entity silver ──integrate──► 4-merged/nodes.jsonl + edges.jsonl
  index.yaml ──┐
  rules.yaml ──┼── classify ──► 4-merged/nodes.jsonl (+ ontology slots)
               └──► publish ──► 5-gold ──► export/neo4j
```

### Layer A — compile (what the ontology says)

1. **Adapter** parses the cached OWL file, strips `owl:Axiom`, enumerates **all** `owl:Class` terms, emits bronze JSONL.
2. **Compile** folds bronze into `index.yaml`: `classes` (label, parents, synonyms) + `restrictions_index`.
3. **Manifest** records `source`, `source_name`, `input_hash` at `cache/{source_name}/ontology-manifest.json`.

The index is a **side cache**. It is not merged into the entity graph. Classify (or future tooling) reads it as a lookup table.

### Layer B — classify (what silicoKG assigns to entities)

1. Load cached `index.yaml` and `classification-rules.yaml`.
2. Backup `nodes.jsonl` → `nodes.pre-classify.jsonl`.
3. Match entity edges against rules; append ontology CURIEs to entity node slots.
4. Optionally propagate restriction fillers from the index (e.g. `so_qualities`).
5. Write `classify-manifest.json`.

Classify controls **which** indexed terms appear on **which** entity nodes. It does not control how much of the OWL enters the index — that is always the full file.

### What “full ingestion” means here

| Included in bronze / index | Not included (v1) |
| --- | --- |
| Every `owl:Class` in the file | OWL individuals / instances |
| `rdfs:label`, named `rdfs:subClassOf` parents | `equivalentClass`, `disjointWith` |
| `oboInOwl:*Synonym` | Most annotation properties |
| `someValuesFrom` restrictions on `subClassOf` | `allValuesFrom`, cardinality, union/intersection |
| | OWL DL reasoning, ancestor closure |
| | Ontology terms as merged-graph nodes (see below) |

To put ontology structure **inside** the merged graph (`OntologyTerm` nodes + `subClassOf` edges in Neo4j), add a transform → silver → integrate track. That is a separate extension; this plan stops at index + entity annotation.

---

## Conventions (same as NCBI)

Every source uses **`source`** + **`source_name`**:

| Field | Ontology example | Entity example |
| --- | --- | --- |
| `source` | `obo` | `ncbi` |
| `source_name` | `obo-so`, `obo-go`, … | `ncbi-gene-info` |

**Cache layout** (shared by HTTP fetch and compiled artifacts):

```
universe/cache/{source_name}/
  so.owl                      # raw file (name from ingest config)
  index.yaml                  # compiled index
  ontology-manifest.json      # input_hash, stats
```

**Per-run bronze:**

```
universe/{run_id}/2-bronze/{source_name}/records.jsonl
```

Adding a new ontology = new ingest config entry + new adapter under `sources/{source}/{module}/`. Same pipeline code, different `source_name`.

**Do not:** bulk-load raw OWL to Neo4j, parse OWL at classify time, or use ontology CURIEs as entity `@type`.

**Naming note:** `pipeline/integrate/classify.py` splits silver fragments into nodes/edges. Ontology annotation lives in `pipeline/ontology/classify/` — different stage.

---

## Fixed decisions

| Topic | Choice |
| --- | --- |
| Scope | Full OWL file — all `owl:Class` terms, no subset config |
| Format | OWL/XML (or RDF/XML); strip `owl:Axiom` before extract |
| Bronze discriminant | `row_kind`: `"class"` \| `"restriction"` |
| Classify writes | In-place `4-merged/nodes.jsonl`; backup `nodes.pre-classify.jsonl` |
| Index location | `universe/cache/{source_name}/index.yaml` |

---

## Adding a new ontology (checklist)

Use this when registering `obo-go`, `obo-mondo`, etc.

1. Add ingest entry to [`pipeline/ingest/config.yaml`](../../pipeline/ingest/config.yaml):
   ```yaml
   obo-go:
     url: http://purl.obolibrary.org/obo/go.owl
     ttl_seconds: 604800
     format: owl
     raw_filename: go.owl
   ```
2. Add namespace prefix to [`schemas/prefixes.yaml`](../../schemas/prefixes.yaml) if missing.
3. Create `sources/obo/go/` — schema, adapter, register in [`sources/registry.py`](../../sources/registry.py).
4. Run ontology refresh (ingest → validate → compile).
5. *(Optional)* Add classify rules and entity slots if this ontology annotates entities.

---

## Implementation steps

Follow in order. Steps 1–2 are largely done. Steps 3–7 can use a tiny TTL fixture before wiring a real OWL file. Step 8 connects the first adapter (`obo-so`).

---

### Step 1 — Dependencies and ingest config

**Why:** Ingest fetches/caches the OWL file; compile and adapter need rdflib.

**Do:**

1. Add `rdflib` to [`requirements.txt`](../../requirements.txt); `pip install rdflib`.
2. For each ontology, add an entry to [`pipeline/ingest/config.yaml`](../../pipeline/ingest/config.yaml).
3. Add namespace prefixes to [`schemas/prefixes.yaml`](../../schemas/prefixes.yaml).

**Example (SO — already present):**

```yaml
obo-so:
  url: http://purl.obolibrary.org/obo/so.owl
  ttl_seconds: 604800
  format: owl
  raw_filename: so.owl
```

**Verify:** `pip show rdflib` succeeds.

---

### Step 2 — Path helpers

**Why:** Compile and classify resolve paths by `source_name`, matching NCBI ingest cache.

**Do:** Confirm [`pipeline/paths.py`](../../pipeline/paths.py) has:

- `source_cache_dir(source_name)` → `universe/cache/{source_name}/`
- `ontology_index_path(source_name)` → `…/index.yaml`
- `ontology_manifest_path(source_name)` → `…/ontology-manifest.json`
- `merged_nodes_pre_classify(run_id)`, `classify_manifest(run_id)`

**Verify:**

```bash
PYTHONPATH=. python3 -c "
from pipeline.paths import DEFAULT_PATHS as p
print(p.ontology_index_path('obo-so'))
"
# → .../universe/cache/obo-so/index.yaml
```

---

### Step 3 — Preprocess + restriction parser

**Why:** OBO OWL files use reified axioms and nested restrictions; strip axioms and extract `someValuesFrom` before bronze/compile.

**Do:** Create:

| File | Implements |
| --- | --- |
| `pipeline/ontology/compile/preprocess.py` | `strip_owl_axioms(graph)` |
| `pipeline/ontology/compile/restrictions.py` | `extract_restrictions_for_class(graph, iri)` — `someValuesFrom` on `subClassOf` |
| `pipeline/ontology/tests/fixtures/minimal-ontology.ttl` | Small multi-class fixture |
| `pipeline/ontology/tests/test_compile_restrictions.py` | Assert restriction rows |

**Verify:**

```bash
pytest pipeline/ontology/tests/test_compile_restrictions.py -q
```

---

### Step 4 — Compile engine + CLI

**Why:** Downstream stages read a compact YAML index, not bronze JSONL or raw OWL.

**Do:** Create:

| File | Implements |
| --- | --- |
| `pipeline/ontology/compile/models.py` | `OntologyClass`, `OntologyIndex` dataclasses |
| `pipeline/ontology/compile/engine.py` | Bronze rows → `classes` + `restrictions_index`; validate fillers exist |
| `pipeline/ontology/cli.py` | `compile --source obo --source-name <name> --run-id <id>` |
| `pipeline/ontology/__main__.py` | `python -m pipeline.ontology` entry |

CLI is generic — same flags for every ontology source.

**Verify** (hand-built bronze for one source):

```bash
PYTHONPATH=. python -m pipeline.ontology.cli compile --source obo --source-name obo-so --run-id test-ontology
cat universe/cache/obo-so/index.yaml
```

---

### Step 5 — OWL adapter (full file)

**Why:** Connects real cached OWL to bronze rows. This is the per-ontology piece; compile/classify stay shared.

**Do:** For each ontology, create `sources/{source}/{module}/`:

| File | Purpose |
| --- | --- |
| `{source_name}.schema.yaml` | LinkML: `OntologyClassRow`, `OntologyRestrictionRow` |
| `adapter.py` | `@register` adapter; `source = "{source_name}"` |

Register module in [`sources/registry.py`](../../sources/registry.py).

**Adapter flow (full file, no subset):**

1. Parse cached OWL from `source_cache_dir(source_name)`.
2. `strip_owl_axioms()`.
3. Query all `?term a owl:Class` where `term` is a named URI in the ontology namespace.
4. Per class: yield class row — `term_id` (CURIE), `iri`, `label`, named `subClassOf` parents, synonyms.
5. Per class: yield restriction rows via `extract_restrictions_for_class`.
6. Write `ontology_manifest_path(source_name)` with `source`, `source_name`, `input_hash`, term counts.

Namespace and CURIE prefix are adapter constants (e.g. SO adapter: namespace `http://purl.obolibrary.org/obo/SO_`, prefix `SO`).

**Verify — ontology refresh:**

```bash
PYTHONPATH=. python -m pipeline.ingest.cli --source obo --source-name obo-so --run-id ontology-refresh-001
PYTHONPATH=. python -m pipeline.validate.cli --source obo --source-name obo-so --run-id ontology-refresh-001
PYTHONPATH=. python -m pipeline.ontology.cli compile --source obo --source-name obo-so --run-id ontology-refresh-001
wc -l universe/ontology-refresh-001/2-bronze/obo-so/records.jsonl
```

Expect class row count ≈ total `owl:Class` terms in `so.owl` (plus restriction rows).

---

### Step 6 — Domain schema + merge slots *(if using classify)*

**Why:** Publish and integrate must accept ontology annotation slots on entity nodes.

**Do:** For each ontology that annotates entities, add slots and attach to target classes. SO example:

1. Add to [`schemas/slots.yaml`](../../schemas/slots.yaml): `so_types`, `so_qualities` (multivalued CURIE lists).
2. Attach to `Gene` in [`schemas/domain/gene-or-gene-product.yaml`](../../schemas/domain/gene-or-gene-product.yaml).
3. Add slot names to `MULTIVALUED_NODE_SLOTS` in [`pipeline/identity/constants.py`](../../pipeline/identity/constants.py).

Other ontologies get their own slot names (e.g. `go_terms`) or a shared generic slot — decide per use case.

**Verify:** Entity node with annotation slots passes publish without quarantine.

---

### Step 7 — Classify engine + rules *(if annotating entities)*

**Why:** Entity graph edges imply ontology types; classify applies rules against the full cached index.

**Do:** Create:

| File | Implements |
| --- | --- |
| `schemas/ontology/classification-rules.yaml` | Rule definitions per ontology / use case |
| `pipeline/ontology/classify/rules.py` | Load YAML → `ClassificationRule` |
| `pipeline/ontology/classify/engine.py` | Backup, match edges, append slots, write manifest |
| `pipeline/ontology/classify/runner.py` | Wrapper for `pipeline.run` |
| `pipeline/ontology/classify/cli.py` | Standalone `--run-id` CLI |
| `pipeline/ontology/tests/test_classify_*.py` | Fixture merged graph + assertions |

**Engine logic:**

1. Load `ontology_index_path(source_name)` and rules; fail if `assign_class` missing from index.
2. Copy `nodes.jsonl` → `nodes.pre-classify.jsonl`.
3. Match edges; collect entity ids by `gene_role` (`subject` or `object`).
4. Append `assign_class` to target slot; optionally propagate restriction fillers.
5. Write `nodes.jsonl` and `classify-manifest.json`.

Rules select **which entities** get **which** terms. The index already contains all terms from the full OWL.

**Verify:**

```bash
pytest pipeline/ontology/tests/ -q
```

---

### Step 8 — Wire classify in pipeline.run *(if annotating entities)*

**Why:** Entity E2E runs call classify between integrate and publish.

**Do:**

1. In [`pipeline/run/runner.py`](../../pipeline/run/runner.py):
   - Add `"classify"` to `RUN_LEVEL_STAGES`.
   - Add `_run_classify(ctx, run_id)` — read `source`, `source_name`, `rules` from `ctx.stage_args["classify"]`.
   - Resolve index via `paths.ontology_index_path(source_name)`.
2. Update run YAML:

```yaml
stages:
  - ingest
  - validate
  - transform
  - integrate
  - classify
  - publish
  - export_neo4j

classify:
  source: obo
  source_name: obo-so
  rules: schemas/ontology/classification-rules.yaml
```

**Verify:**

```bash
PYTHONPATH=. python -m pipeline.ontology.classify.cli --run-id test-x
```

---

### Step 9 — Neo4j export *(if annotating entities)*

**Why:** Gold CSV must expose ontology annotation arrays.

**Do:** Add slot names to `ARRAY_PROPERTY_KEYS` in [`pipeline/export/neo4j/engine.py`](../../pipeline/export/neo4j/engine.py).

**Verify:** Gene CSV header includes annotation columns when present.

---

### Step 10 — E2E checklist

**Ontology refresh** (once per ontology, or when OWL changes):

```bash
PYTHONPATH=. python -m pipeline.ingest.cli --source obo --source-name obo-so --run-id ontology-refresh-001
PYTHONPATH=. python -m pipeline.validate.cli --source obo --source-name obo-so --run-id ontology-refresh-001
PYTHONPATH=. python -m pipeline.ontology.cli compile --source obo --source-name obo-so --run-id ontology-refresh-001
```

**Entity run** (requires cached index + classify in run YAML):

```bash
PYTHONPATH=. python -m pipeline.run.cli pipeline/run/examples/ncbi-gene-info-summary.yaml
```

Checklist:

- [ ] `universe/cache/{source_name}/ontology-manifest.json` has `input_hash`, `source_name`, term counts
- [ ] `universe/cache/{source_name}/index.yaml` contains all expected classes
- [ ] `4-merged/classify-manifest.json` records rule counts (if classify enabled)
- [ ] Entity nodes have annotation slots where rules match
- [ ] Neo4j CSV exports annotation arrays

---

## Data shapes

**Bronze class row:**

```json
{"row_kind":"class","term_id":"SO:0000287","iri":"http://purl.obolibrary.org/obo/SO_0000287","label":"fusion_gene","parents":["SO:0000704"],"synonyms":[]}
```

**Bronze restriction row:**

```json
{"row_kind":"restriction","class_id":"SO:0000287","restriction_type":"some_values_from","property_iri":"http://purl.obolibrary.org/obo/so#has_quality","property_id":"so:has_quality","filler_id":"SO:0000806"}
```

**Compiled index** (`universe/cache/{source_name}/index.yaml`):

```yaml
version: 1
source_name: obo-so
input_hash: "<sha256>"
classes:
  SO:0000287:
    label: fusion_gene
    parents: [SO:0000704]
restrictions_index:
  SO:0000287:
    - { type: some_values_from, property: so:has_quality, filler: SO:0000806 }
```

---

## Files to create

**Shared (once):**

```
pipeline/ontology/
  __init__.py
  __main__.py
  cli.py
  compile/          preprocess.py, restrictions.py, models.py, engine.py
  classify/         rules.py, engine.py, runner.py, cli.py
  tests/
```

**Per ontology** (repeat for each `source_name`):

```
sources/obo/so/
  adapter.py
  obo-so.schema.yaml

sources/obo/go/     # future
  adapter.py
  obo-go.schema.yaml
```

**Edit existing:** `requirements.txt`, `pipeline/ingest/config.yaml`, `schemas/prefixes.yaml`, `sources/registry.py`, and (if classify) `schemas/slots.yaml`, `pipeline/run/runner.py`, `pipeline/export/neo4j/engine.py`.

(`pipeline/paths.py` — already done.)

---

## Out of scope (v1)

Subset/BFS term selection, OBO flat file format, OWL → Neo4j bulk load, OWL DL reasoning, ancestor closure, `OntologyTerm` nodes in merged graph.

---

## References

- SO OWL (first instance): http://purl.obolibrary.org/obo/so.owl
- GO POC (axiom-strip pattern): `kg-medallion-architecture-poc/pipelines/silver/go_loader.py`
