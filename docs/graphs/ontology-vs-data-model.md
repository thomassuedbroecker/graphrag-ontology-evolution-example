# Ontology vs data model

[← All versions](README.md)

Both describe "the graph", but they answer different questions:

- The **data model** says **how** facts are stored: node labels, edge types, properties, constraints and indexes in Neo4j.
- The **ontology** says **what** a fact means: which kinds of things exist, which dependencies may hold between them, in which direction, and what each dependency does and does not claim.

| | Data model | Ontology |
| --- | --- | --- |
| Question | How do we store and query a fact? | What does this fact mean, and is it allowed? |
| In this repo | `Document`, `Entity`, `Revision`; `MENTIONS`, `RELATION`, `HAS_REVISION` ([storage model](README.md#how-it-is-stored)) | Entity types and relation endpoints in [v1.json](../../data/ontologies/v1.json) / [v2.json](../../data/ontologies/v2.json) |
| Enforced by | Neo4j constraints and the importer's Cypher ([store.py](../../src/local_graphrag/store.py)) | The validator ([data.py](../../src/local_graphrag/data.py)), before anything is written |
| Changes when | Storage or query needs change | The domain needs a new kind of thing or a new dependency |
| Owner | Developer | Operator / model owner, with review |

## The same fact, two views

*Lunar Excursions requires completion of Lunar Surface Safety training* (v2 proposal):

| View | Representation |
| --- | --- |
| Ontology | `Service —REQUIRES→ Training`: the service depends on the training as a prerequisite |
| Data model | `(:Entity {type:'Service'})-[:RELATION {kind:'REQUIRES'}]->(:Entity {type:'Training'})` |

To the data model, `REQUIRES` is just a string in `kind`. All domain edges look the same: one `RELATION` from one `Entity` to another. That is why v2 needs no Neo4j schema change ([design decision](../architecture.md#graph-storage-model)).

## Why the dependency meaning is key

Since the data model treats every edge the same, **only the ontology carries the meaning of a dependency**. That meaning has three parts:

1. **Direction.** `Lunar Excursions REQUIRES Lunar Surface Safety` says the service depends on the training. Reversed, it would say the training depends on the service. Storage accepts both. Only the ontology's `[subject, object]` pair says which one is valid.
2. **Allowed endpoints.** `OFFERS` connects only Company → Service, and `VISITS` connects only Service → Destination. The data model would store any `kind` between any two entities.
3. **Scope of the claim.** Each relation states what it implies and what it leaves out:

| Relation | Means | Does not mean |
| --- | --- | --- |
| OFFERS (Company → Service) | The company offers the service | Exclusivity, price, availability dates |
| VISITS (Service → Destination) | The service goes to the destination | That every service has a destination (none is invented) |
| REQUIRES (Service → Training), v2 | The service has the training as a prerequisite | "Before departure", completion status, enforcement |

### Retrieval does not check meaning

`graph_context` expands **one hop in either direction, over any `kind`** ([store.py](../../src/local_graphrag/store.py#L119-L128)). It returns `subject, relation, object` triples, and the answering model reads the dependency from them. If a triple carries the wrong meaning, the agent states it in the answer with a citation that looks valid. Retrieval cannot catch that. Only the ontology check at import time stops it.

### A valid shape with the wrong meaning

The training fact could be squeezed into v1 by typing the training as a `Destination`:

```text
Lunar Excursions —VISITS→ Lunar Surface Safety   # passes v1 validation
```

Every type and endpoint is allowed, and Neo4j stores it without complaint. But the meaning is false: the agent would answer that the excursion *travels to* a safety course, and the prerequisite would be lost. This is why the repo rejects the training data under v1 and proposes a new dependency (`REQUIRES`) in [v2](v2.md) instead of reusing a relation that fits the shape.

## Which layer does a change touch?

| Change | Data (instances) | Ontology | Data model |
| --- | --- | --- | --- |
| New service, e.g. Lunar Photography Tours | Yes | No: a new name is not a new type | No |
| Retire a service | Yes | No | No |
| Training requirement | Yes | Yes: new `Training` type and `REQUIRES` dependency (v2) | No |
| Native Neo4j labels per type, or a new index | No | No | Yes |

Rule of thumb: if the source states a **new kind of dependency**, it is an ontology change and must be reviewed, even when the data model could already store it.
