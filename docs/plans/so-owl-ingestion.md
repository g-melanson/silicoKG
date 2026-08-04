# Sequence Ontology (SO) — instance notes

SO-specific implementation details for the generic OWL plan.

**Canonical plan:** [`owl-ontology-ingestion.md`](./owl-ontology-ingestion.md) (full-file ingestion, no subsets)

---

## SO identifiers

| Field | Value |
| --- | --- |
| `source` | `obo` |
| `source_name` | `obo-so` |
| OWL URL | http://purl.obolibrary.org/obo/so.owl |
| Namespace | `http://purl.obolibrary.org/obo/SO_` |
| CURIE prefix | `SO` |

## SO adapter constants

In `sources/obo/so/adapter.py`:

```python
ONTOLOGY_NAMESPACE = "http://purl.obolibrary.org/obo/SO_"
TERM_ID_PREFIX = "SO"
```

Extract every `owl:Class` URI in that namespace — no subset config.

## SO entity annotation (classify)

Slots on `Gene`:

- `so_types` — assigned SO class CURIEs
- `so_qualities` — restriction fillers propagated from index

Example rule (`schemas/ontology/classification-rules.yaml`):

```yaml
rules:
  - id: readthrough-parent-is-fusion-gene
    assign_class: SO:0000287
    target_entity: Gene
    when:
      edge:
        class: GeneHasReadthroughParent
        gene_role: object
    propagate_restrictions: true
```

Edge source: [`sources/ncbi/ncbi_gene_group/`](../../sources/ncbi/ncbi_gene_group/)

## SO test fixture

Minimal TTL for restriction parser tests (`pipeline/ontology/tests/fixtures/minimal-ontology.ttl`):

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix so: <http://purl.obolibrary.org/obo/so#> .
@prefix SO: <http://purl.obolibrary.org/obo/SO_> .

SO:0000704 a owl:Class ; rdfs:label "gene" .
SO:0000806 a owl:Class ; rdfs:label "fusion" ; rdfs:subClassOf SO:0000733 .
SO:0000733 a owl:Class ; rdfs:label "feature_attribute" .
SO:0000287 a owl:Class ; rdfs:label "fusion_gene" ;
  rdfs:subClassOf SO:0000704 ,
    [ a owl:Restriction ; owl:onProperty so:has_quality ; owl:someValuesFrom SO:0000806 ] .
```

## SO refresh commands

```bash
PYTHONPATH=. python -m pipeline.ingest.cli --source obo --source-name obo-so --run-id so-refresh-001
PYTHONPATH=. python -m pipeline.validate.cli --source obo --source-name obo-so --run-id so-refresh-001
PYTHONPATH=. python -m pipeline.ontology.cli compile --source obo --source-name obo-so --run-id so-refresh-001
```
