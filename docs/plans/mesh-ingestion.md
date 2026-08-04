# MeSH descriptor ingestion — implementation guide

Ingest a **filtered subset** of NIH MeSH descriptor records from the annual XML release, emit bronze term + hierarchy edge rows, and wire them through the standard silicoKG pipeline (transform → integrate → publish).

**Source:** `nih-mesh` (`sources/nih/nih_mesh/`)  
**Raw file:** [desc2026.xml](https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml)  
**Closest template:** Gene Ontology (`obo-go`) — term rows + edge rows in one JSONL stream  
**Related:** [`owl-ontology-ingestion.md`](./owl-ontology-ingestion.md), [`pipeline/README.md`](../../pipeline/README.md), [`identity-contract.md`](./identity-contract.md)

---

## What you are building

| Piece | What it is | Where it lives |
| --- | --- | --- |
| **Ingest config** | URL, cache TTL, raw filename | [`pipeline/ingest/config.yaml`](../../pipeline/ingest/config.yaml) |
| **Adapter** | Stream-parse XML, filter by tree prefix, emit bronze rows | [`sources/nih/nih_mesh/adapter.py`](../../sources/nih/nih_mesh/adapter.py) |
| **Bronze schema** | LinkML validation for descriptor + edge rows | [`sources/nih/nih_mesh/nih-mesh.schema.yaml`](../../sources/nih/nih_mesh/nih-mesh.schema.yaml) |
| **Transform** | Map bronze → domain `MeSHDescriptor` nodes + hierarchy edges | [`sources/nih/nih_mesh/nih-mesh.transform.yaml`](../../sources/nih/nih_mesh/nih-mesh.transform.yaml) |
| **Domain schema** | Gold-tier node/edge classes | `schemas/domain/` (new MeSH section) |
| **Run example** | End-to-end pipeline YAML | `pipeline/run/examples/test-mesh.yaml` |

Unlike `obo-so` (full-file → cached index → classify), MeSH goes through the **full entity pipeline**: ingest → validate → transform → integrate → publish. We are building graph nodes and edges, not entity annotations.

---

## Background: what MeSH is (read this first)

MeSH (Medical Subject Headings) is NLM's controlled vocabulary for indexing biomedical literature (MEDLINE/PubMed). silicoKG cares about **Descriptors** — the subject headings used to tag articles.

NLM publishes MeSH in several formats. We use **XML Descriptors** because it is the maintained production format and includes concept/term structure that ASCII/ELHILL formats flatten.

### XML is human-legible, not hierarchy-nested for trees

XML MeSH uses descriptive tags (`<DescriptorUI>`, `<TreeNumber>`) instead of short mnemonics (`UI`, `MN`). Files are larger than legacy formats; that is intentional.

Important distinction for engineers:

| Structure | Where it lives | What it means |
| --- | --- | --- |
| **Descriptor → Concept → Term** | Nested XML inside one `<DescriptorRecord>` | Synonymy and concept-level metadata **within** a record |
| **Tree hierarchy** | Flat `<TreeNumber>` strings on the descriptor | Broader/narrower relationships **between** descriptor records |

These are **two different hierarchies**. Do not confuse them.

---

## MeSH has three levels inside each record

Every `<DescriptorRecord>` follows this pattern:

```
DescriptorRecord
├── DescriptorUI          (persistent ID, e.g. D000005)
├── DescriptorName/String (preferred label, e.g. "Abdomen")
├── Annotation            (descriptor-level note)
├── TreeNumberList        (browse hierarchy positions — see below)
├── ConceptList
│   └── Concept           (PreferredConceptYN="Y" or "N")
│       ├── ConceptUI
│       ├── ScopeNote     (concept-level definition)
│       └── TermList
│           └── Term
│               ├── TermUI
│               └── String  (synonym or preferred term)
└── … (SeeRelated, PharmacologicalAction, etc.)
```

**Descriptor** — the indexed subject heading. One record = one descriptor.

**Concept** — a meaning shared by synonymous terms. A descriptor can have multiple concepts (e.g. preferred + narrower concepts). Concepts are **not** separate records in the XML file.

**Term** — a string label. Terms sharing a `<ConceptUI>` are strictly synonymous. All terms in a descriptor are equivalent for MEDLINE indexing, even across concepts.

Example (simplified):

```
Cardiomegaly [Descriptor D006332]
  Cardiomegaly [Concept, Preferred]
    Cardiomegaly, Enlarged Heart, Heart Enlargement [Terms]
  Cardiac Hypertrophy [Concept, Narrower]
    Cardiac Hypertrophy, Heart Hypertrophy [Terms]
```

**What to extract for v1:**

| Field | Attach level | Include in bronze? |
| --- | --- | --- |
| `DescriptorUI` | Descriptor | Yes — primary key |
| `DescriptorName/String` | Descriptor | Yes — display label |
| `TreeNumber` | Descriptor | Yes — filter + hierarchy |
| `ScopeNote` | Concept (preferred) | Yes — optional definition |
| Synonym terms | Concept/Term | Yes — flatten to list |
| `Annotation` | Descriptor | Optional v2 |
| `SeeRelatedDescriptor` | Descriptor | Out of scope v1 |
| Qualifiers, SCRs | Separate files | Out of scope v1 |

Use `<String>` under the **preferred concept's** `<TermList>` for synonyms. Skip permuted terms (`IsPermutedTermYN="Y"`) unless you have a specific search use case.

---

## MeSH tree hierarchy (the part we filter on)

Descriptors are also organized into **16 category trees** (A = anatomy, B = organisms, C = diseases, D = chemicals, …). Within each category, descriptors are arranged up to ~13 levels deep. These "trees" are browse/search aids.

Each descriptor has one or more `<TreeNumber>` values, e.g.:

```xml
<TreeNumber>D05.750.078.730.250</TreeNumber>
<TreeNumber>D12.776.210.500.100</TreeNumber>
```

**Critical facts:**

1. **Tree numbers are not nested XML.** The hierarchy is encoded in the string itself (`D05.750.078` is parent of `D05.750.078.730.250`).
2. **A descriptor may appear in multiple trees** (polyhierarchy). Actins is under both `D05.…` and `D12.…`.
3. **Tree numbers are locators, not semantic IDs.** `D12.776.641` and `D12.644.641` sharing `641` does not imply they are related.
4. **Tree numbers can change** when MeSH is revised annually. DescriptorUIs are stable.

Parent tree number = drop the last dot-separated segment:

```
D05.500.562.374  →  parent: D05.500.562
D05.875          →  parent: D05
D05              →  parent: (none — category root)
```

Each tree number maps to **exactly one descriptor** (the descriptor that "owns" that position). To find the parent descriptor for tree `T`, look up which descriptor owns `parent(T)`.

---

## Project scope: partial subtree ingestion

We do **not** ingest all ~30k descriptors. We ingest descriptors whose tree numbers fall under an allowlist of **prefix roots**, plus one explicit **leaf** tree number.

Current allowlist (from exploratory work in [`test.py`](../../test.py)):

```python
_LEAF = ["D05.875"]          # Protein Aggregates (D066329) — not under any _ROOT prefix
_ROOT = [
    "D05.500",               # Enzymes (branch)
    "D06.472",               # …
    "D08.244",
    "D08.622",
    "D08.811",
    "D12.644",
    "D12.776",
    "D12.888",
]
```

**Matching rule:** keep a descriptor if **any** of its tree numbers satisfies:

```python
def matches(tree: str, prefixes: list[str]) -> bool:
    return any(tree == p or tree.startswith(p + ".") for p in prefixes)
```

Apply to `_ROOT + _LEAF` combined. This includes the descriptor at each root prefix itself (exact match), not only strict descendants.

**Scale check (2026 MeSH):** the eight `_ROOT` prefixes cover ~5,220 descriptors. Adding `D05.875` adds one more. Manageable for full pipeline runs.

Store the allowlist in adapter config (YAML or constants module), not hard-coded only in `test.py`.

---

## How it works in silicoKG

```
desc2026.xml
  ──ingest (adapter)──► 1-staging/nih-mesh/records.jsonl
  ──validate──────────► 2-bronze/nih-mesh/records.jsonl
  ──transform─────────► 3-silver/nih-mesh/fragments.jsonl
  ──integrate─────────► 4-merged/nodes.jsonl + edges.jsonl
  ──publish───────────► 5-gold/
```

### Adapter algorithm (two logical passes, one XML stream)

MeSH XML is ~100MB+. Use **`iterparse` with streaming** — never load the full document into memory.

**Pass A — collect descriptors (during the single stream):**

For each `<DescriptorRecord>`:

1. Parse `DescriptorUI`, preferred label, tree numbers, preferred-concept scope note, synonym strings.
2. If any tree number matches the allowlist → store in `descriptors[ui]` and register each tree number in `tree_to_ui[tree] = ui`.
3. Call `elem.clear()` after processing to free memory.

**Pass B — emit edges (after stream, or second in-memory pass over collected data):**

For each kept descriptor and each of its tree numbers `T`:

1. Walk `T → parent(T) → parent(parent(T)) → …`
2. At each step, if `parent(T)` is owned by a descriptor also in `descriptors` → emit hierarchy edge.
3. Stop when parent tree has no owning descriptor (common near category roots like `D05`).

**Edge strategy (v1 — minimal):**

- Only emit edges where **both** subject and object descriptors are in the filtered set.
- Include `tree_number` on the edge row so polyhierarchy is preserved (Actins has different parents under `D05` vs `D12`).
- Do **not** create virtual nodes for tree numbers without descriptors.

---

## Fixed decisions

| Topic | Choice | Rationale |
| --- | --- | --- |
| Raw format | XML Descriptors (`desc{year}.xml`) | Production NLM format; includes concepts/terms |
| Parsing | `xml.etree.ElementTree.iterparse` | Stdlib, streaming, already prototyped |
| Scope | Prefix-filtered subtree, not full MeSH | Product requirement |
| Primary ID | `DescriptorUI` (e.g. `D066329`) | Stable across MeSH years |
| Hierarchy ID | `TreeNumber` strings | MeSH browse hierarchy is tree-scoped |
| Bronze discriminant | `row_kind`: `"descriptor"` \| `"edge"` | Matches GO pattern |
| Edge predicate | `mesh:broaderDescriptor` (or `silkg:SUBCLASS_OF`) | Align with domain schema naming |
| Qualifiers / SCRs | Out of scope v1 | Separate XML files, different use case |
| Concept relations | Out of scope v1 | Within-record; tree hierarchy is the priority |
| SeeRelated / PharmacologicalAction | Out of scope v1 | Cross-descriptor associations, not taxonomy |

---

## Conventions (same as other sources)

| Field | Value |
| --- | --- |
| `source` | `nih` |
| `source_name` | `nih-mesh` |

**Cache layout:**

```
universe/cache/nih-mesh/
  desc2026.xml
```

**Per-run artifacts:**

```
universe/{run_id}/1-staging/nih-mesh/records.jsonl
universe/{run_id}/2-bronze/nih-mesh/records.jsonl
universe/{run_id}/3-silver/nih-mesh/fragments.jsonl
```

Register the adapter in [`sources/registry.py`](../../sources/registry.py).

---

## Implementation steps

Follow in order. Steps 1–3 can be validated with [`test.py`](../../test.py) before wiring the pipeline.

---

### Step 0 — Read NLM docs and inspect one record

**Why:** Build intuition for XML shape before writing extraction code.

**Do:**

1. Read [MeSH XML Data Elements](https://www.nlm.nih.gov/mesh/xml_data_elements.html) — focus on `DescriptorRecord`, `TreeNumber`, `Concept`, `Term`.
2. Read [MeSH Tree Structures](https://www.nlm.nih.gov/mesh/intro_trees.html) — focus on polyhierarchy and tree number semantics.
3. Run the prototype streamer:

   ```bash
   PYTHONPATH=. python test.py
   ```

   Inspect one `<DescriptorRecord>`: find `DescriptorUI`, `TreeNumberList`, `ConceptList/Concept/TermList`.

**Verify:** You can point to where label, tree numbers, and synonyms live in the XML.

---

### Step 1 — Ingest config + cache

**Why:** Pipeline fetch/cache layer must know where to download the XML file.

**Do:** Add to [`pipeline/ingest/config.yaml`](../../pipeline/ingest/config.yaml):

```yaml
nih-mesh:
  url: https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml
  ttl_seconds: 604800          # refresh weekly; MeSH updates annually
  format: xml
  raw_filename: desc2026.xml
```

Add `mesh:` prefix to [`schemas/prefixes.yaml`](../../schemas/prefixes.yaml) if missing (URI: `https://id.nlm.nih.gov/mesh/` or project convention).

**Verify:**

```bash
PYTHONPATH=. python -m pipeline.ingest.cli --source nih --source-name nih-mesh --run-id mesh-smoke-001
ls -lh universe/cache/nih-mesh/desc2026.xml
```

---

### Step 2 — Bronze schema

**Why:** Validate adapter output before transform.

**Do:** Complete [`sources/nih/nih_mesh/nih-mesh.schema.yaml`](../../sources/nih/nih_mesh/nih-mesh.schema.yaml).

Suggested classes (can import shared enums from `schemas/style/` or define locally):

**`NIHMeshDescriptorRow`** (`row_kind: descriptor`):

| Slot | Type | Notes |
| --- | --- | --- |
| `row_kind` | enum | `"descriptor"` |
| `descriptor_ui` | string | e.g. `D066329` |
| `label` | string | Preferred descriptor name |
| `tree_numbers` | string[] | All tree positions for this descriptor |
| `scope_note` | string | From preferred concept; optional |
| `synonyms` | string[] | Non-preferred terms from all concepts |

**`NIHMeshEdgeRow`** (`row_kind: edge`):

| Slot | Type | Notes |
| --- | --- | --- |
| `row_kind` | enum | `"edge"` |
| `subject_id` | string | Child `descriptor_ui` |
| `object_id` | string | Parent `descriptor_ui` |
| `tree_number` | string | Tree branch this edge belongs to |
| `predicate_id` | string | Constant, e.g. `mesh:broaderDescriptor` |

**Verify:** Schema loads without LinkML errors:

```bash
PYTHONPATH=. python -c "from linkml_runtime import SchemaView; SchemaView('sources/nih/nih_mesh/nih-mesh.schema.yaml')"
```

---

### Step 3 — Adapter

**Why:** Core extraction logic — filter + hierarchy reconstruction.

**Do:** Implement [`sources/nih/nih_mesh/adapter.py`](../../sources/nih/nih_mesh/adapter.py).

**Skeleton:**

```python
@register
class NIHMeshAdapter(BaseAdapter):
    source = "nih-mesh"
    schema_path = Path(__file__).with_name("nih-mesh.schema.yaml")

    def target_class_for_record(self, record: dict) -> str:
        if record.get("row_kind") == "edge":
            return "NIHMeshEdgeRow"
        return "NIHMeshDescriptorRow"

    def parse(self, path: Path) -> Iterator[dict]:
        allowlist = load_allowlist()  # from config or constants
        descriptors, tree_to_ui = {}, {}

        for record in self._iter_descriptors(path):
            if not self._matches_allowlist(record["tree_numbers"], allowlist):
                continue
            descriptors[record["descriptor_ui"]] = record
            for t in record["tree_numbers"]:
                tree_to_ui[t] = record["descriptor_ui"]

        for ui, desc in descriptors.items():
            yield {**desc, "row_kind": "descriptor"}

        for ui, desc in descriptors.items():
            for tree in desc["tree_numbers"]:
                for edge in self._ancestor_edges(tree, tree_to_ui, descriptors):
                    yield edge
```

**Helper functions to implement:**

| Function | Purpose |
| --- | --- |
| `_iter_descriptors(path)` | `iterparse` → yield parsed dicts; `elem.clear()` each record |
| `_parse_descriptor_record(elem)` | XPath-like `find`/`findall` for UI, name, trees, concepts |
| `_parent_tree(tree)` | `"D05.500.562.374"` → `"D05.500.562"` |
| `_matches_allowlist(trees, prefixes)` | Prefix filter |
| `_ancestor_edges(tree, tree_to_ui, descriptors)` | Walk parents; yield edge dicts |

**Parsing tips for juniors:**

- Tags are plain strings (`"DescriptorRecord"`) — no namespace prefix in ElementTree.
- Use `.//TreeNumber` to find all tree numbers regardless of list wrapper depth.
- Preferred concept: `Concept[@PreferredConceptYN='Y']` — in ElementTree, check `elem.get("PreferredConceptYN") == "Y"`.
- Decode XML entities (`&amp;` → `&`) — ElementTree handles this automatically in `.text`.

Register in [`sources/registry.py`](../../sources/registry.py).

**Verify:**

```bash
PYTHONPATH=. python -m pipeline.ingest.cli --source nih --source-name nih-mesh --run-id mesh-smoke-002
PYTHONPATH=. python -m pipeline.validate.cli --source nih --source-name nih-mesh --run-id mesh-smoke-002

# Expect ~5.2k descriptor rows + ~similar edge rows
wc -l universe/mesh-smoke-002/2-bronze/nih-mesh/records.jsonl
head -3 universe/mesh-smoke-002/2-bronze/nih-mesh/records.jsonl
```

**Sanity checks:**

- [ ] `D066329` (Protein Aggregates) present — matches `D05.875`
- [ ] `D000199` (Actins) present with multiple tree numbers
- [ ] No descriptor outside allowlist
- [ ] Edges reference only ingested descriptor UIs

---

### Step 4 — Domain schema

**Why:** Transform emits fragments validated at publish time.

**Do:** Add to `schemas/domain/` (new file or section in `silicokg.yaml`):

```yaml
MeSHDescriptor:
  description: A MeSH topical descriptor from the NIH MeSH vocabulary.
  attributes:
    id:
      identifier: true
    name:
      range: string
    definition:
      range: string
    synonyms:
      range: string
      multivalued: true

MeSHBroaderThan:
  description: Immediate broader descriptor in a MeSH tree branch.
  attributes:
    id:
      identifier: true
    subject:
      range: MeSHDescriptor
    object:
      range: MeSHDescriptor
    tree_number:
      range: string
```

Decide URI pattern (e.g. `silkg:MeSHDescriptor:mesh:D066329`) and document in [`identity-contract.md`](./identity-contract.md).

---

### Step 5 — Transform

**Why:** Map bronze rows to domain fragments for integrate.

**Do:** Complete [`sources/nih/nih_mesh/nih-mesh.transform.yaml`](../../sources/nih/nih_mesh/nih-mesh.transform.yaml).

Follow [`sources/obo/go/obo-go.transform.yaml`](../../sources/obo/go/obo-go.transform.yaml):

- `NIHMeshDescriptorRow` → `MeSHDescriptor` node fragment
- `NIHMeshEdgeRow` → `MeSHBroaderThan` edge fragment (subject narrower, object broader — confirm direction with MeSH convention)

**Verify:**

```bash
PYTHONPATH=. python -m pipeline.transform.cli --source nih --source-name nih-mesh --run-id mesh-smoke-002
head -5 universe/mesh-smoke-002/3-silver/nih-mesh/fragments.jsonl
```

---

### Step 6 — Run config + integrate/publish

**Why:** End-to-end proof with other sources if needed.

**Do:** Create `pipeline/run/examples/test-mesh.yaml`:

```yaml
run_id: test-mesh
sources:
  - nih-mesh
stages:
  - ingest
  - validate
  - transform
  - integrate
  - publish
```

For a combined run (MeSH + genes), add `nih-mesh` to an existing run's `sources` list.

**Verify:**

```bash
PYTHONPATH=. python -m pipeline.run.cli pipeline/run/examples/test-mesh.yaml
wc -l universe/test-mesh/5-gold/nodes.jsonl universe/test-mesh/5-gold/edges.jsonl
```

---

### Step 7 — Tests

**Why:** Lock in filter logic and edge derivation — the easy parts to regress.

**Do:** Add `sources/nih/nih_mesh/tests/` or `pipeline/ingest/tests/test_mesh_adapter.py`:

| Test case | Assert |
| --- | --- |
| Prefix match | `D05.500.049` matches root `D05.500` |
| Exact root match | `D05.500` matches root `D05.500` |
| Non-match | `D05.875` does not match root `D05.500` (but matches `_LEAF`) |
| Parent tree | `_parent_tree("D05.500.562.374") == "D05.500.562"` |
| Polyhierarchy | Actins yields edges under both `D05.…` and `D12.…` branches |
| Edge boundary | No edge to descriptor outside filtered set |

Use a **fixture XML** with 3–5 synthetic `<DescriptorRecord>` elements — do not commit the full desc2026.xml.

**Verify:**

```bash
pytest sources/nih/nih_mesh/tests/ -q
```

---

## Data shapes

**Bronze descriptor row:**

```json
{
  "row_kind": "descriptor",
  "descriptor_ui": "D066329",
  "label": "Protein Aggregates",
  "tree_numbers": ["D05.875"],
  "scope_note": "…",
  "synonyms": []
}
```

**Bronze edge row (tree-scoped):**

```json
{
  "row_kind": "edge",
  "subject_id": "D000199",
  "object_id": "D009124",
  "tree_number": "D05.750.078.730.250",
  "predicate_id": "mesh:broaderDescriptor"
}
```

**Silver node fragment (after transform):**

```json
{
  "@type": "MeSHDescriptor",
  "id": "silkg:MeSHDescriptor:mesh:D066329",
  "name": "Protein Aggregates",
  "definition": "…",
  "sources": ["nih-mesh"]
}
```

---

## Edge cases (teaching notes)

### 1. Two hierarchies, one record

Concepts inside a record (e.g. "Cardiac Hypertrophy" narrower than "Cardiomegaly") are **not** separate descriptors. They do not appear in tree browse. For v1, flatten synonyms across concepts; do not emit concept-concept edges unless you add `ConceptRelation` parsing later.

### 2. Polyhierarchy

When a descriptor has tree numbers in multiple branches, emit **one edge per (tree_number, parent) pair**. Do not collapse to a single parent — you would lose branch context.

### 3. Missing parent descriptors

Parent tree `D05` may not have a descriptor record. Stop walking; do not invent placeholder nodes in v1.

### 4. Leaf outside root prefixes

`D05.875` (Protein Aggregates) is not under any `_ROOT` prefix. The explicit `_LEAF` entry ensures it is included. Document this whenever the allowlist changes.

### 5. Annual MeSH updates

Bumping `desc2026.xml` → `desc2027.xml` requires updating ingest config URL/filename. DescriptorUIs are stable; tree numbers may shift. Re-run ingest and diff counts after each annual release.

### 6. XML size and memory

Always `elem.clear()` after processing each `DescriptorRecord` in `iterparse`. Without this, memory grows with file size.

---

## Optional future work (out of scope v1)

| Feature | Notes |
| --- | --- |
| Cached tree index | `universe/cache/nih-mesh/index.yaml` for fast re-filtering with different allowlists |
| MeSH RDF source | Pre-built `parentTreeNumber` edges; heavier dependency |
| Qualifiers (`qual2026.xml`) | Subheadings paired with descriptors |
| SCRs (supplementary concepts) | Daily-updated; separate pipeline |
| `SeeRelatedDescriptor` edges | Associative, not hierarchical |
| `PharmacologicalAction` | Drug → action links |
| Concept-level `ConceptRelation` | Within-record narrower/broader |
| Full MeSH ingestion | Remove prefix filter |

---

## Files to create or edit

**Create:**

```
sources/nih/nih_mesh/
  adapter.py              # implement
  nih-mesh.schema.yaml    # complete
  nih-mesh.transform.yaml # complete
  tests/
    fixtures/minimal-desc.xml
    test_adapter.py

pipeline/run/examples/
  test-mesh.yaml

schemas/domain/
  mesh.yaml               # or section in silicokg.yaml
```

**Edit:**

```
pipeline/ingest/config.yaml
sources/registry.py
schemas/prefixes.yaml
```

**Retire (after adapter works):**

```
test.py                   # promote logic into adapter; keep or delete
```

---

## E2E checklist

- [ ] `universe/cache/nih-mesh/desc2026.xml` cached
- [ ] Bronze row count ≈ 5,220 descriptors (+ edges)
- [ ] `D066329` / `D05.875` present
- [ ] Validate passes with zero quarantine
- [ ] Transform emits `MeSHDescriptor` + `MeSHBroaderThan` fragments
- [ ] Publish accepts gold nodes/edges
- [ ] Unit tests cover prefix filter and parent-tree walk

---

## References

- [Download MeSH Data](https://www.nlm.nih.gov/databases/download/mesh.html)
- [MeSH XML Data Elements](https://www.nlm.nih.gov/mesh/xml_data_elements.html)
- [Introduction to MeSH in XML Format](https://www.nlm.nih.gov/mesh/xml_mesh.html)
- [MeSH Tree Structures](https://www.nlm.nih.gov/mesh/intro_trees.html)
- [Concept Structure in MeSH](https://www.nlm.nih.gov/mesh/concept_structure.html)
- [MeSH RDF tree numbers](https://hhs.github.io/meshrdf/tree-numbers)
- silicoKG GO template: [`sources/obo/go/adapter.py`](../../sources/obo/go/adapter.py)
- Prototype streamer: [`test.py`](../../test.py)
