# Labs: build, change and migrate a GraphRAG graph

Labs 1–8 form the core path; Labs 9–12 are optional extensions. Run them in order: each starts from the previous lab’s graph state. Commands run from the repository root.

| Lab | You do | Ontology | Facts after |
| --- | --- | --- | --- |
| [1. Initial setup](01-initial-setup.md) | Start a fresh demo database and import the baseline | v1 | 4 |
| [2. Initial data, initial question](02-initial-question.md) | Ask Q1 and compare retrieval with the answer | v1 | 4 |
| [3. Add data that fits](03-add-fitting-data.md) | Add a new service; ask Q1 and the new Q2 | v1 | 5 |
| [4. Add data that does not fit](04-add-non-fitting-data.md) | See which data the rules reject, and why one version *does* fit | v1 | 5 |
| [5. Update the graph definition](05-update-graph-definition.md) | Compare ontology v1 with v2 | v1 (v2 approved) | 5 |
| [6. Migrate the existing graph data](06-migrate-graph-data.md) | Move every stored document to v2 | **v2** | 5 |
| [7. Add the new data](07-add-new-data.md) | Import the training dependency under v2 | v2 | 6 |
| [8. All questions](08-all-questions.md) | Ask Q1, Q2 and the new Q3 | v2 | 6 |
| [9. Breaking ontology change](09-breaking-ontology-change.md) | Rename and redefine relations in a v3 proposal; find the invalid facts | v2 (v3 refused) | 6 |
| [10. Ontology impact analysis](10-ontology-impact-analysis.md) | List the affected entities, facts, documents, questions and code before migrating; gate on it | v2 | 6 |
| [11. AI-assisted relationship discovery](11-ai-assisted-relationship-discovery.md) | Let the LLM propose cross-document relations; gate, review, import one | v2 | 7 |
| [12. Validation and regression](12-validation-and-regression.md) | Compare with a reviewed ground truth and a full rebuild; catch a regression | v2 | 7 |

The four questions (catalog: [questions.json](../data/scenarios/regression/questions.json)):

| ID | Question | Introduced in |
| --- | --- | --- |
| Q1 | Which destination can Galaxium Travels customers visit? | Lab 2 |
| Q2 | Which services does Galaxium Travels offer? | Lab 3 |
| Q3 | Which training does a Lunar Excursions customer need before departure? | Lab 4 (text only), Lab 8 (graph) |
| Q4 | Which services take customers to the Moon? | Lab 10 (impact), Lab 11 (graph) |

## Lab tools and data (Labs 9–12)

The four helpers read the graph; discovery also writes proposal files. Import graph changes explicitly with `graphrag ingest` or `graphrag migrate`.

| Script | Lab | Needs |
| --- | --- | --- |
| [lab_fact_check.py](../scripts/lab_fact_check.py) | 9 | Neo4j |
| [lab_impact.py](../scripts/lab_impact.py) | 10 | Neo4j, embedding model (`--no-questions`: Neo4j only) |
| [lab_discover.py](../scripts/lab_discover.py) | 11 | Neo4j, chat model (`--slots-only`: Neo4j only) |
| [lab_regression.py](../scripts/lab_regression.py) | 12 | Nothing with `--offline`; Neo4j and embedding model; `--answers` also MCP and chat model |

Shared helpers are in [lab_graph.py](../scripts/lab_graph.py). The data lives next to the other scenarios: [breaking-change](../data/scenarios/breaking-change), [relationship-discovery](../data/scenarios/relationship-discovery) and [regression](../data/scenarios/regression).

## Prerequisites

Lab 1 lists the tools to install and runs the first start, which downloads the models and packages. Run every command from the repository root. Use only the demo database: Lab 1 deletes it.

## How to read the expected results

- `graphrag inspect`, `ingest` plans and `migrate` plans should match the recorded document revisions and facts with the same files, embedding model name and dimensions (timestamps differ). `graphrag search` always runs retrieval and expansion, but scores and ranking can vary with model artifacts and runtime versions.
- `graphrag ask` uses a local LLM. Its wording varies from run to run. Each lab says what a correct answer must contain and what to look out for.
- Every lab ends with **Check yourself**. Try to answer the items first, then open **Show answers** below the list.
- Excerpts shorten long JSON with `…`. Python warnings from third-party packages are omitted.

## Everything is versioned

| What | Version identifier | Where you see it |
| --- | --- | --- |
| Graph definition (ontology) | `"version": "1"`, `"2"` in [data/ontologies](../data/ontologies); v2 declares `"extends": "1"` | `graphrag inspect` → `ontology`, `ontology_history` |
| Source text | `source_version`: SHA-256 of the mapped source section | Document JSON |
| Document | `ontology_version` label plus a content revision (SHA-256 of document, embedding model, dimensions) | `graphrag inspect` → `documents[].revision` |
| Document history | One `Revision` node per imported or migrated version, with the full JSON snapshot | `graphrag inspect` → `documents[].revisions` |
| Fact | `RELATION` edge with owning `document_id` and `revision` | `graphrag inspect` → `facts` |
| Answering prompt | `answering-v1` | `graphrag ask --trace` → `prompt_version` |
| Discovery prompt | `discovery-v1` | `lab_discover.py` → `prompt_version` |
| Ground truth | `1.0.0` | [ground-truth.json](../data/scenarios/regression/ground-truth.json) → `version` |

Each lab’s before/after table shows the expected revisions and fact count. [Lab 12](12-validation-and-regression.md) compares incremental and rebuilt content.

## Rules for inserting data into the graph

Data reaches the graph **only** through `graphrag ingest --apply` and `graphrag migrate --apply`. Both enforce the gates below. No free-form JSON, extra properties or nested payloads are stored; they are rejected, not ignored.

| # | Gate | Rule | Code | Lab |
| --- | --- | --- | --- | --- |
| 1 | Mapping | Only the reviewed *Primary Services* section is mapped; unknown service names stop `prepare` | [prepare.py](../src/local_graphrag/prepare.py) `SERVICES` | 1, 3 |
| 2 | Document format | Exactly the fields `id, title, text, source, ontology_version, entities, facts` (+ optional `source_version, evidence`); entity, fact and evidence objects have fixed fields; IDs are lowercase slugs; `text` is a prose passage, not embedded JSON | [data.py](../src/local_graphrag/data.py) `DOCUMENT_FIELDS`, `ITEM_FIELDS`, `validate` | 4 |
| 3 | Ontology | Entity types and relation endpoints must exist in the graph's **active** ontology, and the document's `ontology_version` must match it | `validate`, [store.py](../src/local_graphrag/store.py) `active_ontology`, `apply` | 4, 6, 7 |
| 4 | Evidence | Optional quotes must appear in the text and back a declared fact | `validate` | 7 |
| 5 | Plan before write | `ingest` without `--apply` shows `added_facts` / `removed_facts`; review them first | `Store.plan` | 3, 4, 7 |
| 6 | Atomic write | Conflicting entity definitions roll back the whole import | `Store._write` | — |
| 7 | Migration | Target must be `approved`, must `extend` the active version and be additive; every stored document is revalidated under it | `check_migration`, `Store._migration` | 6 |

Gates 2 and 3 check **structure, not truth**. Lab 4 shows the consequence: a document can pass every gate and still hide a dependency in its text.

**Bypass:** Neo4j Browser and the shared Neo4j credential can write directly and skip every gate. The rules are a code boundary, not a database permission (see [limitations](../README.md#limitations)).

## Reset

```bash
./scripts/stop.sh --delete-data && ./scripts/start.sh   # back to the state after Lab 1
```

`./scripts/stop.sh` keeps data. Restarting with `start.sh` on **v1 reapplies the baseline company and lunar documents**, undoing the new-service update while retaining extra documents and revision history. Avoid restarting between Labs 3–6, or reapply Lab 3 before continuing. Once the graph is on v2 it prints `Graph is on ontology 2; skipped importing data/documents` and does not overwrite anything.
