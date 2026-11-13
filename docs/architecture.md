# Architecture

The two paths below share Neo4j and Ollama. See the [limitations](../README.md#limitations) before extending the example.

## Principle: separate reading from writing

The answering agent **reads** knowledge. A separate, operator-driven maintenance path **prepares, validates and writes** it. A model proposal never grants permission to change the ontology or the database.

![Answering reads through MCP; maintenance validates before writing; Ollama embeds both.](architecture-assets/overview.svg)

## Components

| Component | Responsibility | Code |
| --- | --- | --- |
| Answering agent | Pick tools, compose a cited answer. No write tools. | [agent.py](../src/local_graphrag/agent.py), [prompts.py](../src/local_graphrag/prompts.py) |
| Read-only MCP server | `search_documents(question, limit≤10)` and `graph_context(document_id)` (one hop, ≤50 facts) | [server.py](../src/local_graphrag/server.py), [store.py](../src/local_graphrag/store.py) |
| Preparer | Reviewed mapping of the company Markdown's *Primary Services* section to JSON documents | [prepare.py](../src/local_graphrag/prepare.py) |
| Validator | Reject fields outside the fixed document format, non-slug IDs and JSON passed as text; check types, relation endpoints, duplicate and conflicting IDs, `source_version` format and optional evidence quotes against the graph's active ontology | [data.py](../src/local_graphrag/data.py), [v1.json](../data/ontologies/v1.json) |
| Importer | Plan create/update/unchanged plus added/removed facts per document; embed changed documents; write them in one transaction | [store.py](../src/local_graphrag/store.py) |
| Neo4j 5.26 | Documents, entities, relations, vectors and revision snapshots | [compose.yaml](../compose.yaml) |
| Ollama | `qwen3:8b` chat, `nomic-embed-text` embeddings (768 dimensions) | runs on the host |

## Graph storage model

The [storage diagram and field guide](graphs/README.md#how-it-is-stored) show how documents, entities and revisions connect.

**Design decision: generic `Entity` and `RELATION`.** Domain types (Company, Service…) are the `Entity.type` property, and domain relations (OFFERS, VISITS) are the `RELATION.kind` property, not Neo4j labels or relationship types.

- *Why:* the ontology lives in a versioned JSON file and is enforced by the validator. Adding Training/REQUIRES in v2 needs no Neo4j schema change, and the one-hop expansion query works for any ontology.
- *Cost:* Cypher is less idiomatic (`[r:RELATION {kind:'OFFERS'}]` instead of `[:OFFERS]`) and Neo4j cannot use label indexes per type. Fine at demo size; revisit for large graphs.
- *Consequence:* storage accepts any `kind` between any entities, so the meaning and direction of each dependency are defined only by the ontology. See [ontology vs data model](graphs/ontology-vs-data-model.md).

## Workflows

### Setup and update under v1

`graphrag prepare` → `graphrag validate` → `ingest.sh` (plan with fact diff) → `ingest.sh --apply`. The [data lineage](data-lineage.md) shows the real data after each step. The importer:

1. validates **all** documents before touching the database;
2. compares each document's hash (content + embedding model + dimensions) with the stored one;
3. embeds only changed documents, **before** opening the write transaction;
4. in one transaction, replaces the facts and mentions owned by each changed document and keeps a content-addressed `Revision` snapshot;
5. rejects an existing entity ID whose name or type changed (the whole transaction rolls back).

A repeat import of identical data reports every document `unchanged` and writes nothing. `start.sh` reapplies the two baseline documents while the graph is on v1: it can undo the service update, but does not delete extra documents or revision history. On v2 it skips that import. Continue the labs without restarting between steps; use `stop.sh --delete-data` for a complete reset.

A new service name (Lunar Photography Tours) is a new **instance** of Service and fits v1. A new name is not a new type.

### Ask

The [retrieval diagram](graphs/README.md#how-retrieval-uses-the-graph) shows the two read steps. The prompt asks for `search_documents` first, then `graph_context`, and to cite `document_id` and `source`. The model decides whether to follow it. Measured behaviour is in [experiment results](results.md#recorded-run-13-november-2026).

### Data that needs a new ontology

A source says Lunar Excursions *requires* Lunar Surface Safety training. That needs a Training type and a REQUIRES relation, so v1 rejects it. Free-form JSON carrying the same information is rejected too: documents have a fixed set of fields. [v2](../data/ontologies/v2.json) adds exactly those two elements, is `approved` and `extends` v1.

The graph stores its active definition as an `Ontology` node; the importer validates against it, not against a built-in version. `graphrag migrate` refuses unless the target is approved, extends the active version and is additive. It then relabels and revalidates every current revision snapshot, writes new `Revision` nodes, and switches the active `Ontology` in one transaction. Embeddings are reused because the text does not change. Lab 10 checks current snapshots against a proposed ontology without applying it. Breaking changes require a rebuild; migration simulation and approval records are not implemented. Walkthrough: [Labs 4–7](../labs/README.md).

### Optional experiments (Labs 9–12)

The helpers in `scripts/lab_*.py` read current revision snapshots: they check facts against a target ontology, report impact, propose relationships with an LLM, and compare the graph with reference fixtures. They are teaching tools outside the application CLI. Discovery writes proposal files only; ingestion remains an explicit operator action. Regression rebuilds expected content in memory with `--offline`; the live path separately checks Neo4j and retrieval.

## Security boundaries

- All endpoints must be loopback; Neo4j ports bind to `127.0.0.1` ([config.py](../src/local_graphrag/config.py), [compose.yaml](../compose.yaml)).
- MCP exposes no write or arbitrary-Cypher tool; tool inputs are length- and range-checked.
- The prompt tells the model to treat retrieved text as evidence, never as instructions.
- The MCP HTTP endpoint has no authentication: any local process can call its two read-only tools. Acceptable on loopback for a demo; not for a shared host.
- MCP and importer share one database credential. A production design would use a read-only database role for MCP.
- The `.env.example` password is a demo value, acceptable only because Neo4j is loopback-only.
