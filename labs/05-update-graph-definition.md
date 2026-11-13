# Lab 5: Update the graph definition

[← Lab 4](04-add-non-fitting-data.md) · [Labs](README.md) · Next: [Lab 6](06-migrate-graph-data.md)

**Goal:** define how the new dependency is modelled and compare the new graph definition with the active one. The graph itself does not change in this lab.

| | Before | After |
| --- | --- | --- |
| Active ontology (graph) | 1 | 1 |
| Available definitions | [v1.json](../data/ontologies/v1.json) (baseline) | + [v2.json](../data/ontologies/v2.json) (approved, `extends: "1"`) |
| Facts | 5 | 5 |

## Step 1: Read both definitions

v1 ([v1.json](../data/ontologies/v1.json)):

```json
{ "version": "1", "status": "baseline",
  "entity_types": ["Company", "Destination", "Service"],
  "relations": { "OFFERS": ["Company", "Service"], "VISITS": ["Service", "Destination"] } }
```

v2 ([v2.json](../data/ontologies/v2.json)):

```json
{ "version": "2", "status": "approved", "extends": "1",
  "entity_types": ["Company", "Destination", "Service", "Training"],
  "relations": { "OFFERS": ["Company", "Service"], "VISITS": ["Service", "Destination"],
                 "REQUIRES": ["Service", "Training"] } }
```

| Field | Meaning |
| --- | --- |
| `version` | The label every document must carry to be imported under this definition |
| `status` | `baseline` (the definition for an empty graph), `proposed` (under review, cannot be migrated to), `approved` (may be migrated to) |
| `extends` | The only version a graph may migrate **from** |

## Step 2: Compare the definitions

```bash
.venv/bin/graphrag ontology-diff data/ontologies/v1.json data/ontologies/v2.json
```

`ontology-diff` takes two arguments, both paths to ontology JSON files: `old` (the definition you start from) and `new` (the one you compare against it). It reads only the files. It does not need Neo4j or Ollama and does not change the graph. Running it without both paths fails with `the following arguments are required: old, new`.

**Expected result:**

```json
{
  "from": "1",
  "to": "2",
  "added_types": ["Training"],
  "removed_types": [],
  "added_relations": { "REQUIRES": ["Service", "Training"] },
  "removed_relations": [],
  "changed_relations": {},
  "unchanged_relations": ["OFFERS", "VISITS"],
  "compatible": true
}
```

Read it as a review checklist:

| Question | Answer from the diff | Consequence |
| --- | --- | --- |
| Does it add what Lab 4 was missing? | `Training`, `REQUIRES` | The dependency becomes a fact |
| Does it remove or redefine anything? | No (`removed_*`, `changed_relations` empty) | Every v1 document stays valid |
| Is it compatible? | `true` (additive) | Migration is a relabel, no re-extraction needed |

Both additions are needed. A `Training` type without `REQUIRES` still rejects the fact (`Invalid ontology relation`).

## Step 3: Validate the new data against v2, offline

```bash
.venv/bin/graphrag validate --data data/scenarios/training-requirement/candidates \
  --ontology data/ontologies/v2.json
```

**Expected result:**

```text
Validated 1 documents
Validation only: ontology 2 (approved); the importer follows the graph's active ontology (graphrag inspect)
```

## Step 4: Confirm the graph did not change

```bash
.venv/bin/graphrag inspect
```

**Expected result:** `"ontology": "1"`, three documents, five facts, exactly as after Lab 4. A definition file alone changes nothing. Activation is a migration (Lab 6).

## What would block a migration

`graphrag ontology-diff` also shows non-additive changes. To see one, write a throwaway copy of v2 that redefines `VISITS` as `Company → Destination`, and compare it with v1:

```bash
mkdir -p .runtime/lab-05
.venv/bin/python -c '
import json
o = json.load(open("data/ontologies/v2.json"))
o["relations"]["VISITS"] = ["Company", "Destination"]
json.dump(o, open(".runtime/lab-05/v2-breaking.json", "w"), indent=2)
'
.venv/bin/graphrag ontology-diff data/ontologies/v1.json .runtime/lab-05/v2-breaking.json
```

**Expected result** (shortened):

```json
"changed_relations": { "VISITS": { "from": ["Service", "Destination"], "to": ["Company", "Destination"] } },
"unchanged_relations": ["OFFERS"],
"compatible": false
```

The copy is in `.runtime`, outside `data/ontologies`, so it never becomes part of the repository's graph definitions.

Existing `Lunar Excursions VISITS Moon` facts would become invalid. This repo refuses such migrations (`Only additive migrations are supported`). They need a rebuild from the sources.

## Check yourself

- [ ] `compatible: true`, one added type, one added relation.
- [ ] The graph still reports ontology `1`.
