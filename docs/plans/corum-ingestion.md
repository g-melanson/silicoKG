# CORUM human complexes ingestion — implementation guide

Ingest CORUM human protein complexes from the local JSON release, emit bronze complex / membership / function / FCG / evidence rows, and wire them through the standard silicoKG pipeline (transform → integrate → classify → publish → Neo4j export).

**Source:** `corum-human-complexes` (`sources/corum/corum_human_complexes/`)  
**Raw file:** [`data/corum/corum_humanComplexes.json`](../../data/corum/corum_humanComplexes.json) (~5,628 complexes)  
**Closest templates:** HGNC gene groups (`MEMBER_OF` + `GeneGroup`), UniProt GAF (Protein stubs + GO associations), MeSH (multi-`row_kind` JSONL bronze)  
**Related:** [`identity-contract.md`](./identity-contract.md), [`mesh-ingestion.md`](./mesh-ingestion.md), [`pipeline/README.md`](../../pipeline/README.md)

---

## What you are building

| Piece | What it is | Where it lives |
| --- | --- | --- |
| **Ingest config** | Local JSON path + cache TTL | [`pipeline/ingest/config.yaml`](../../pipeline/ingest/config.yaml) |
| **Adapter** | Parse CORUM JSON; emit flattened bronze rows | `sources/corum/corum_human_complexes/adapter.py` |
| **Bronze schema** | LinkML validation for multi-kind rows | `sources/corum/corum_human_complexes/corum-human-complexes.schema.yaml` |
| **Transform** | Map bronze → ProteinComplex / Evidence / Protein / GeneGroup / GO edges | `sources/corum/corum_human_complexes/corum-human-complexes.transform.yaml` |
| **Domain schema** | New `ProteinComplex`, `AnnotatedEvidence`, membership + GO edge classes | `schemas/domain/protein-complexes.yaml` (new) |
| **Classification** | Label Proteins that are complex members as `Subunit` | [`schemas/ontology/classification-rules.yaml`](../../schemas/ontology/classification-rules.yaml) |
| **Neo4j labels** | Extra `CORUM` / `Subunit` labels on export | [`schemas/ontology/so-label-map.yaml`](../../schemas/ontology/so-label-map.yaml) (+ small export/classify support) |
| **Run example** | End-to-end pipeline YAML | `pipeline/run/examples/test-corum.yaml` |

Unlike ontology classify-only sources, CORUM goes through the **full entity pipeline**: ingest → validate → transform → integrate → classify → publish → export.

---

## Background: what CORUM is (read this first)

[CORUM](https://mips.helmholtz-muenchen.de/corum/) is a manually curated database of mammalian protein complexes. Each record is one complex with subunits (UniProt-linked), GO function annotations, PubMed citations, free-text comments, and optional membership in Functional Complex Groups (FCGs).

### Scale (current JSON dump)

| Metric | Count |
| --- | --- |
| Complexes | 5,628 (all `organism: Human`) |
| Subunit links | 18,970 (0 missing `uniprot_id`) |
| Unique UniProt accessions | 5,297 |
| Function → GO annotations | 16,742 |
| FCG memberships | 1,951 |
| Unique FCGs | 42 (`fcg_id` 1–46; sparse) |
| Complex IDs overlapping FCG IDs | 13 — **why FCG IDs must use `CORUM:FCG{n}`** |

### JSON object shape (one complex)

```
complex
├── complex_id, complex_name, synonyms, organism, cell_line, pmid
├── comment_complex | comment_members | comment_disease | comment_drug | comment_drug_formal
├── purification_methods[]          # deferred v1
├── subunits[]
│   └── swissprot.uniprot_id        # primary join key into silKG Proteins
├── functions[]
│   ├── evi, pmid
│   └── go.{go_id, ontology, name}  # molecular_function | cellular_component | biological_process
└── fcgs[]
    └── fcg.{fcg_id, name, go.{go_id, ontology}}
```

Example complex `1` (`BCL6-HDAC4 complex`): subunits `P41182`, `P56524`; GO MF/CC/BP terms; empty `fcgs`.

Example FCG attachment (complex `36`): `fcg_id: 16` → GO:0016192 (vesicle-mediated transport). Each FCG currently maps to **exactly one** GO id in this dump.

---

## Fixed decisions (requirements → graph contract)

| # | Requirement | Decision |
| --- | --- | --- |
| 1 | Namespace `CORUM` + complex ID | ProteinComplex `id` = `CORUM:{complex_id}` (e.g. `CORUM:15`) |
| 2 | One JSON object → ProteinComplex | `@type: ProteinComplex` |
| 3 | Complex description | Concatenate non-empty `comment_complex` + `comment_members` into `description` |
| 4 | New AnnotatedEvidence node | `@type: AnnotatedEvidence`; `id` = `silkg:AnnotatedEvidence:corum:{complex_id}` |
| 5 | Evidence description | Concatenate **all** non-empty `comment_*` fields into `description` |
| 6 | Evidence PMIDs | Deduped union of complex-level `pmid` **and** all `functions[].pmid` → `pubmed_id` (multivalued string) |
| 7 | UniProt entry-point | Subunit join key = UniProt accession → Protein URI `silkg:Protein:9606:{uniprot_id}` (same as UniProt GAF) |
| 8 | Subunit membership | Edge `Protein --silkg:MEMBER_OF--> ProteinComplex` |
| 9 | Subunit class | Classify edge subject Proteins as `Subunit` (Neo4j additional label) |
| 10–11 | Complex → GO | Aspect-specific predicates; edge carries `pubmed_id` |
| 12 | FCG → GeneGroup | GeneGroup `id` = `CORUM:FCG{fcg_id}` (e.g. `CORUM:FCG16`) |
| 13 | Complex → FCG | Edge `ProteinComplex --silkg:MEMBER_OF--> GeneGroup`; edge `pubmed_id` = complex-level PMID |
| 14 | FCG → GO | Edge `GeneGroup --silkg:BROAD_MATCH--> GO term` |
| 15 | CORUM class label | Every CORUM-minted node also exports Neo4j label `CORUM` |

### Predicates and GO object URIs

| CORUM `go.ontology` | Predicate | Object URI |
| --- | --- | --- |
| `biological_process` | `silkg:PARTICIPATES_IN` | `silkg:BiologicalProcess:{go_id}` |
| `cellular_component` | `silkg:ACTIVE_IN` | `silkg:CellComponent:{go_id}` |
| `molecular_function` | `silkg:HAS_FUNCTION` | `silkg:MolecularFunction:{go_id}` |

Use `CellComponent` (not `CellularComponent`) in **URIs** to match UniProt GAF / `pipeline/ontology/go_uri.py`. Domain class may remain `CellularComponent` with id derivation emitting `silkg:CellComponent:…` (same pattern as `obo-go.transform.yaml`).

### Edge direction cheat-sheet

```
Protein  ──MEMBER_OF──►  ProteinComplex  ──MEMBER_OF──►  GeneGroup(CORUM:FCG*)
                              │                              │
                              ├──HAS_EVIDENCE──► AnnotatedEvidence
                              │
                              ├──PARTICIPATES_IN──► BiologicalProcess
                              ├──ACTIVE_IN────────► CellComponent
                              └──HAS_FUNCTION─────► MolecularFunction
                                                     ▲
                              GeneGroup ──BROAD_MATCH─┘
```

### AnnotatedEvidence linkage (required; not in prose requirements)

Emit one evidence node **per complex** and link:

| Edge class | Subject | Predicate | Object |
| --- | --- | --- | --- |
| `ProteinComplexHasEvidence` | `CORUM:{id}` | `silkg:HAS_EVIDENCE` | `silkg:AnnotatedEvidence:corum:{id}` |

Without this edge the evidence node is orphaned.

### Comment concatenation algorithm

```python
def join_comments(*parts: str | None, sep: " ") -> str | None:
    chunks = [p.strip() for p in parts if p and str(p).strip()]
    return sep.join(chunks) or None
```

| Target slot | Fields (in order) |
| --- | --- |
| `ProteinComplex.description` | `comment_complex`, `comment_members` |
| `AnnotatedEvidence.description` | `comment_complex`, `comment_members`, `comment_disease`, `comment_drug`, `comment_drug_formal` |

Treat JSON `null` and empty string `""` as absent. Do not invent separators beyond a single space (or `\n\n` if agents prefer readability — pick one and test stable output).

### PMID normalization

- Store as **decimal strings** without `PMID:` prefix (matches TFLink `pubmed_id` habit): `"11929873"`.
- Coerce JSON integers to string.
- Deduplicate while preserving first-seen order.

### CORUM / Subunit Neo4j labels

Existing export additional labels come from SO CURIEs via [`so-label-map.yaml`](../../schemas/ontology/so-label-map.yaml). CORUM needs **silicoKG-owned** labels outside SO.

**Recommended approach:**

1. Add multivalued string slot `class_labels` (range CURIE/string) on `NamedThing` or on CORUM-touched classes.
2. Transform sets `class_labels: ["silkg:CORUM"]` on every CORUM-minted node (`ProteinComplex`, `AnnotatedEvidence`, `GeneGroup` from FCG).
3. Classification rule annotates member Proteins with `silkg:Subunit` into `class_labels`.
4. Extend label map:

```yaml
additional_labels:
  class_labels:
    silkg:CORUM: CORUM
    silkg:Subunit: Subunit
  # ... existing so_types / so_qualities ...
```

5. **Classify engine gap:** today `annotate.value` must exist in the SO ontology index. Agents must either:
   - relax validation for `silkg:` class-label CURIEs, **or**
   - add a small `schemas/ontology/silkg-class-index.yaml` (or extend required-terms collection) listing `silkg:Subunit` / `silkg:CORUM`.

Do **not** put `CORUM` on UniProt/NCBI Protein nodes via transform stubs alone for requirement 15 — requirement 15 applies to nodes **generated from** CORUM (`ProteinComplex`, `AnnotatedEvidence`, FCG `GeneGroup`). Proteins keep `@type: Protein` and gain `Subunit` via classify; they are not CORUM-sourced nodes.

---

## How it works in silicoKG

```
data/corum/corum_humanComplexes.json
  ──ingest (adapter)──► 1-staging/corum-human-complexes/records.jsonl
  ──validate──────────► 2-bronze/corum-human-complexes/records.jsonl
  ──transform─────────► 3-silver/corum-human-complexes/fragments.jsonl
  ──integrate─────────► 4-merged/nodes.jsonl + edges.jsonl
  ──classify──────────► Subunit labels on member Proteins
  ──publish───────────► 5-gold/
  ──export_neo4j──────► ProteinComplex:CORUM, GeneGroup:CORUM, Protein:Subunit, …
```

### Adapter algorithm

Load JSON array (file is ~tens of MB; full load is fine for v1). For each complex object, emit multiple bronze rows:

| `row_kind` | Cardinality | Purpose |
| --- | --- | --- |
| `complex` | 1 / complex | ProteinComplex + AnnotatedEvidence (+ HAS_EVIDENCE) |
| `subunit` | 1 / subunit | Protein stub + MEMBER_OF complex |
| `function` | 1 / functions[] | Complex → GO edge |
| `fcg` | 1 / fcgs[] | GeneGroup (idempotent) + complex MEMBER_OF group + BROAD_MATCH |

Deduplicate FCG GeneGroup emission either in adapter (seen-set) or rely on integrate node merge on `(id, @type)`. Prefer adapter seen-set for quieter silver.

Human-only filter: skip non-Human if future dumps add other organisms (current dump is all Human).

---

## Conventions

| Field | Value |
| --- | --- |
| `source` | `corum` |
| `source_name` | `corum-human-complexes` |

**Cache layout:**

```
universe/cache/corum-human-complexes/
  corum_humanComplexes.json
```

**Per-run artifacts:**

```
universe/{run_id}/1-staging/corum-human-complexes/records.jsonl
universe/{run_id}/2-bronze/corum-human-complexes/records.jsonl
universe/{run_id}/3-silver/corum-human-complexes/fragments.jsonl
```

Register the adapter in [`sources/registry.py`](../../sources/registry.py). Add `SOURCE_PACKAGE_DIRS` entry in [`pipeline/paths.py`](../../pipeline/paths.py) if package path differs from hyphen→underscore default (`corum_human_complexes` is fine).

---

## URI / identity formulas

| Entity / edge | URI |
| --- | --- |
| ProteinComplex | `CORUM:{complex_id}` |
| AnnotatedEvidence | `silkg:AnnotatedEvidence:corum:{complex_id}` |
| GeneGroup (FCG) | `CORUM:FCG{fcg_id}` |
| Protein (stub / join) | `silkg:Protein:9606:{uniprot_id}` |
| ProteinMemberOfComplex | `silkg:ProteinMemberOfComplex:9606:{uniprot_id}:{complex_id}` |
| ProteinComplexHasEvidence | `silkg:ProteinComplexHasEvidence:{complex_id}` |
| ProteinComplexGOAssociation | `silkg:ProteinComplexGO:{complex_id}:{predicate_local}:{go_id}:{pmid}` |
| ProteinComplexMemberOfFCG | `silkg:ProteinComplexMemberOfFCG:{complex_id}:{fcg_id}` |
| GeneGroupBroadMatchGO | `silkg:GeneGroupBroadMatchGO:FCG{fcg_id}:{go_id}` |

Document these in [`identity-contract.md`](./identity-contract.md) when implementing.

**Prefixes to add** in [`schemas/prefixes.yaml`](../../schemas/prefixes.yaml):

| Prefix | IRI | Notes |
| --- | --- | --- |
| `CORUM` | `https://mips.helmholtz-muenchen.de/corum/#` (or project-chosen) | Complex + FCG CURIEs |
| keep `silkg` | existing | AnnotatedEvidence, predicates, Proteins |

---

## Domain model additions

Create `schemas/domain/protein-complexes.yaml` and import it from [`schemas/domain/silicokg.yaml`](../../schemas/domain/silicokg.yaml).

### Nodes

| Class | Key slots |
| --- | --- |
| `ProteinComplex` | `id`, `name`, `description`, `synonyms`, `tax_id`, `class_labels` |
| `AnnotatedEvidence` | `id`, `description`, `pubmed_id`, `class_labels` |
| `GeneGroup` | **reuse** existing class; CORUM FCGs mint `CORUM:FCG*` ids and set `class_labels` |
| `Protein` | **reuse**; CORUM emits stubs with UniProt accession identity |

Set `tax_id: NCBITaxon:9606` on ProteinComplex (and Protein stubs). Broaden `GeneGroup` description text so it is not HGNC-only.

### Edges

| Class | predicate | Extra slots |
| --- | --- | --- |
| `ProteinMemberOfComplex` | `silkg:MEMBER_OF` | — |
| `ProteinComplexHasEvidence` | `silkg:HAS_EVIDENCE` | — |
| `ProteinComplexGOAssociation` | aspect-specific (see table) | `pubmed_id` |
| `ProteinComplexMemberOfGeneGroup` | `silkg:MEMBER_OF` | `pubmed_id` |
| `GeneGroupBroadMatchGO` | `silkg:BROAD_MATCH` | — |

Add new predicates to [`schemas/enums/edge-predicates.yaml`](../../schemas/enums/edge-predicates.yaml) and [`pipeline/identity/constants.py`](../../pipeline/identity/constants.py):

- `HAS_EVIDENCE`, `PARTICIPATES_IN`, `ACTIVE_IN`, `HAS_FUNCTION`, `BROAD_MATCH`
- `MEMBER_OF` already exists

Synonym parsing: CORUM `synonyms` is either `null` or a single string. Adapter should split on common delimiters if multiple appear (inspect sample values; many are single labels). Emit `synonyms: []` when null.

---

## Implementation steps

Follow in order. Each step lists **Do**, **Files**, and **Verify**.

---

### Step 0 — Inspect source data

**Why:** Confirm field nullability and FCG collision before coding.

**Do:**

```bash
PYTHONPATH=. python -c "
import json
from pathlib import Path
data = json.loads(Path('data/corum/corum_humanComplexes.json').read_text())
print(len(data), sorted(data[0].keys()))
print(json.dumps(data[0], indent=2)[:1200])
c36 = next(c for c in data if c['complex_id']==36)
print(json.dumps(c36['fcgs'], indent=2))
"
```

**Verify:** You can point to `complex_id`, `subunits[].swissprot.uniprot_id`, `functions[].go`, and `fcgs[].fcg.fcg_id`.

---

### Step 1 — Ingest config + prefixes

**Do:** Add to [`pipeline/ingest/config.yaml`](../../pipeline/ingest/config.yaml):

```yaml
corum-human-complexes:
  url: local://data/corum/corum_humanComplexes.json
  ttl_seconds: 604800
  format: json
  raw_filename: corum_humanComplexes.json
```

Add `CORUM` prefix to [`schemas/prefixes.yaml`](../../schemas/prefixes.yaml).

**Verify:** Cache path resolves; ingest can copy/link the local file into `universe/cache/corum-human-complexes/`.

---

### Step 2 — Domain schema + slots

**Do:**

1. Add `class_labels` slot (multivalued string/uriorcurie) to [`schemas/slots.yaml`](../../schemas/slots.yaml) if not present.
2. Create `schemas/domain/protein-complexes.yaml` with node/edge classes above.
3. Import module from `schemas/domain/silicokg.yaml`.
4. Soften HGNC-only wording on `GeneGroup` in `schemas/domain/hgnc-gene-groups.yaml`.
5. Register new predicates in enums + identity constants.

**Verify:**

```bash
PYTHONPATH=. python -c "from linkml_runtime import SchemaView; SchemaView('schemas/domain/silicokg.yaml')"
```

---

### Step 3 — Bronze schema

**Do:** Create `sources/corum/corum_human_complexes/corum-human-complexes.schema.yaml`.

Suggested classes:

**`CorumComplexRow`** (`row_kind: complex`)

| Slot | Notes |
| --- | --- |
| `complex_id` | int/string stable key |
| `complex_name` | → `name` |
| `synonyms` | list |
| `pmid` | optional string |
| `description` | pre-joined complex description **or** raw comment fields |
| `evidence_description` | pre-joined all comments |
| `pubmed_ids` | pre-deduped list for evidence |
| `tax_id` | constant `9606` |

Prefer **adapter-side join/dedupe** of comments and PMIDs so transform exprs stay simple.

**`CorumSubunitRow`** (`row_kind: subunit`)

| Slot | Notes |
| --- | --- |
| `complex_id` | |
| `uniprot_id` | required |
| `gene_name` / `protein_name` | optional Protein stub enrichment |
| `tax_id` | `9606` |

**`CorumFunctionRow`** (`row_kind: function`)

| Slot | Notes |
| --- | --- |
| `complex_id`, `go_id`, `ontology`, `pmid`, `evi` | |

**`CorumFcgRow`** (`row_kind: fcg`)

| Slot | Notes |
| --- | --- |
| `complex_id`, `fcg_id`, `fcg_name`, `go_id`, `ontology`, `pmid` | `pmid` from parent complex |

**Verify:** SchemaView loads.

---

### Step 4 — Adapter

**Do:** Implement package:

```
sources/corum/
  __init__.py
  corum_human_complexes/
    __init__.py
    adapter.py
    parse.py                 # optional helpers
    corum-human-complexes.schema.yaml
    corum-human-complexes.transform.yaml
    tests/
      fixtures/mini_complexes.json
      test_adapter.py
```

Skeleton:

```python
@register
class CorumHumanComplexesAdapter(BaseAdapter):
    source = "corum-human-complexes"
    schema_path = Path(__file__).with_name("corum-human-complexes.schema.yaml")
    ingest_required_fields = ()

    def target_class_for_record(self, record: dict) -> str:
        return {
            "complex": "CorumComplexRow",
            "subunit": "CorumSubunitRow",
            "function": "CorumFunctionRow",
            "fcg": "CorumFcgRow",
        }[record["row_kind"]]

    def parse(self, path: Path, *, ctx=None):
        ...
```

Register module path in [`sources/registry.py`](../../sources/registry.py) `_ADAPTER_MODULES`.

**Fixture:** 2–3 complexes including: multi-subunit, multi-GO aspects, one with FCG, one with disease comment, one with null comments.

**Verify:**

```bash
pytest sources/corum/corum_human_complexes/tests/ -q
```

Expected rough bronze counts on full file: ~5,628 complex + ~18,970 subunit + ~16,742 function + ~1,951 fcg ≈ **43k rows**.

---

### Step 5 — Transform

**Do:** Author `corum-human-complexes.transform.yaml` class_derivations:

| Bronze | Silver `@type`(s) |
| --- | --- |
| `CorumComplexRow` | `ProteinComplex`, `AnnotatedEvidence`, `ProteinComplexHasEvidence` |
| `CorumSubunitRow` | `Protein` (stub), `ProteinMemberOfComplex` |
| `CorumFunctionRow` | `ProteinComplexGOAssociation` |
| `CorumFcgRow` | `GeneGroup`, `ProteinComplexMemberOfGeneGroup`, `GeneGroupBroadMatchGO` |

Key exprs (illustrative):

```yaml
ProteinComplex:
  populated_from: CorumComplexRow
  slot_derivations:
    id: { expr: "'CORUM:' + str(complex_id)" }
    name: { expr: "complex_name" }
    description: { expr: "description" }
    tax_id: { expr: "'NCBITaxon:9606'" }
    class_labels: { expr: "['silkg:CORUM']" }

AnnotatedEvidence:
  populated_from: CorumComplexRow
  slot_derivations:
    id: { expr: "'silkg:AnnotatedEvidence:corum:' + str(complex_id)" }
    description: { expr: "evidence_description" }
    pubmed_id: { expr: "pubmed_ids" }
    class_labels: { expr: "['silkg:CORUM']" }

Protein:
  populated_from: CorumSubunitRow
  slot_derivations:
    id: { expr: "'silkg:Protein:9606:' + str(uniprot_id)" }
    protein_accession_version: { expr: "uniprot_id" }
    symbol: { expr: "gene_name" }
    name: { expr: "protein_name" }
    tax_id: { expr: "'NCBITaxon:9606'" }

ProteinMemberOfComplex:
  populated_from: CorumSubunitRow
  slot_derivations:
    subject: { expr: "'silkg:Protein:9606:' + str(uniprot_id)" }
    object: { expr: "'CORUM:' + str(complex_id)" }
    predicate: { expr: "'silkg:MEMBER_OF'" }

# function: case() on ontology → predicate + GO object URI
# fcg GeneGroup id: "'CORUM:FCG' + str(fcg_id)"
```

Map ontology → predicate in transform `case()` or adapter-computed `predicate` column.

**Integrate priority:** Add `corum-human-complexes` to [`schemas/integrate-priorities.yaml`](../../schemas/integrate-priorities.yaml). Protein stubs from CORUM should **lose** to UniProt GAF / gene2refseq on symbol/name (low rank, e.g. `10`). ProteinComplex / AnnotatedEvidence / CORUM GeneGroups are CORUM-authoritative.

**Verify:** Transform unit test on fixture: assert URI formulas, predicate map, comment joins, FCG id collision avoidance (`CORUM:16` ≠ `CORUM:FCG16`).

---

### Step 6 — Classification rule (Subunit)

**Do:** Append to [`schemas/ontology/classification-rules.yaml`](../../schemas/ontology/classification-rules.yaml):

```yaml
  - id: protein-member-of-complex-is-subunit
    when:
      edge:
        class: ProteinMemberOfComplex
        role: subject
    actions:
      - annotate:
          target_entity: Protein
          slot: class_labels
          value: silkg:Subunit
```

Implement the classify/label-map support noted under Fixed decisions so `silkg:Subunit` is accepted and exports as Neo4j label `Subunit`.

**Verify:** On a mini integrate+classify run, a Protein that appears in a CORUM subunit edge has `class_labels` containing `silkg:Subunit`; Neo4j CSV partition includes `Protein__Subunit` (or equivalent).

---

### Step 7 — Run example + E2E

**Do:** Create `pipeline/run/examples/test-corum.yaml`:

```yaml
run_id: test-corum
sources:
  - source: corum
    source_name: corum-human-complexes
  - source: uniprot
    source_name: uniprot-gaf          # Protein authority merge
  - source: obo
    source_name: obo-go               # GO term nodes for edge endpoints

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

publish:
  schema: schemas/domain/silicokg.yaml

export_neo4j:
  stub_nodes: true   # allow GO / Protein endpoints if partial run
```

For a fuller smoke, add `ncbi-gene-refseq-to-uniprot` / gene2refseq if Protein merge paths need them; UniProt GAF alone is enough to prove UniProt identity join.

**Verify checklist:**

- [ ] `CORUM:1` node `@type: ProteinComplex`, name `BCL6-HDAC4 complex`
- [ ] Description excludes null member comment; evidence description includes disease text when present
- [ ] `silkg:AnnotatedEvidence:corum:1` has pubmed_id including `11929873`
- [ ] Edges `silkg:Protein:9606:P41182 -[MEMBER_OF]-> CORUM:1`
- [ ] Function edges use correct predicates per aspect and carry pubmed_id
- [ ] `CORUM:FCG16` GeneGroup exists; complexes member-of it; BROAD_MATCH to GO
- [ ] No node id `CORUM:16` used for an FCG
- [ ] Export labels include `CORUM` on complex/evidence/FCG nodes and `Subunit` on member proteins
- [ ] Publish validates against umbrella domain schema

---

## Edge cases (teaching notes)

### 1. FCG id vs complex id collision

Numeric overlap exists (e.g. `16`). Never mint FCG GeneGroups as `CORUM:{fcg_id}`. Always `CORUM:FCG{fcg_id}`.

### 2. Multiple PMIDs per complex

Complex-level `pmid` can differ from `functions[].pmid`. Evidence node gets the **union**. Function edges keep the **function-row** pmid only. FCG membership edges use complex-level pmid (CORUM does not attach a separate FCG citation in this JSON).

### 3. Empty comments

Many complexes have `comment_members: null` or `""`. Joiner must yield `null`/omit empty descriptions rather than blank strings.

### 4. Synonyms type variance

~half of records have `synonyms: null`, half a string. Always normalize to a list in bronze.

### 5. Protein stubs without UniProt GAF

If a CORUM UniProt is absent from other sources, integrate still keeps the CORUM Protein stub (identity is UniProt accession). Export may need `stub_nodes: true` for incomplete runs; full production runs should already contain UniProt proteins.

### 6. GO aspect typos / case

Normalize ontology strings to the three expected values; quarantine function rows with unknown ontology.

### 7. Stoichiometry / purification / drugs

Present in JSON (`stoechiometrie`, `purification_methods`, gene drugs/OMIM). **Out of scope v1** unless product asks.

### 8. External CURIE node ids

`CORUM:*` ids are intentional external-style CURIEs (requirement). Neo4j label inference that assumes `silkg:Class:…` ([`pipeline/load/neo4j/engine.py`](../../pipeline/load/neo4j/engine.py)) must not be the sole label source — export already partitions by `@type`. Confirm load/export paths do not drop non-`silkg:` node ids.

---

## Optional future work (out of scope v1)

| Feature | Notes |
| --- | --- |
| Purification method edges | PSI-MI (`mi_id`) nodes/edges |
| Cell line annotation | Slot or ontology xref |
| Disease / drug comments as structured edges | Requires additional ontologies |
| Stoichiometry on MEMBER_OF | Slot on membership edge |
| Non-human CORUM | Taxon-aware Protein URIs |
| Streaming JSON parse | Only if file size grows substantially |

---

## Files to create or edit

**Create:**

```
sources/corum/corum_human_complexes/
  __init__.py
  adapter.py
  parse.py                              # optional
  corum-human-complexes.schema.yaml
  corum-human-complexes.transform.yaml
  tests/fixtures/mini_complexes.json
  tests/test_adapter.py
  tests/test_transform.py

schemas/domain/protein-complexes.yaml
pipeline/run/examples/test-corum.yaml
docs/plans/corum-ingestion.md           # this file
```

**Edit:**

```
pipeline/ingest/config.yaml
sources/registry.py
schemas/prefixes.yaml
schemas/slots.yaml                      # class_labels (if new)
schemas/domain/silicokg.yaml            # import protein-complexes
schemas/domain/hgnc-gene-groups.yaml    # GeneGroup description
schemas/enums/edge-predicates.yaml
pipeline/identity/constants.py
schemas/integrate-priorities.yaml
schemas/ontology/classification-rules.yaml
schemas/ontology/so-label-map.yaml
pipeline/ontology/classify/engine.py    # allow silkg class_labels (if needed)
docs/plans/identity-contract.md         # URI formulas
```

---

## Agent execution order (summary)

1. **Schema + identity** — domain classes, slots, prefixes, predicates, identity-contract rows.  
2. **Bronze + adapter** — flatten JSON; fixture tests for comments/PMIDs/FCG ids.  
3. **Transform** — all node/edge derivations; UniProt Protein URI parity with GAF.  
4. **Integrate wiring** — priorities, registry, ingest config, run YAML.  
5. **Classify + labels** — Subunit rule + CORUM/Subunit Neo4j label map support.  
6. **E2E smoke** — `test-corum` run; count assertions vs scale table; spot-check `CORUM:1` and `CORUM:FCG16`.

Do not invent ProteinComplex ids under `silkg:ProteinComplex:…`. Do not connect subunits via Entrez/gene symbol when UniProt is present. Do not collapse FCG GeneGroups into complex ids.
