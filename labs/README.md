# Labs: build, change and migrate a GraphRAG graph

Lab set **version 1.0.0** · recorded 13 November 2026 on Apple M4 Max, `qwen3:8b`, `nomic-embed-text` (768 dimensions).

Eight labs, run in order. Each one starts from the graph state the previous lab left behind. Every lab lists the commands, the **expected result** for each step, and the versions before and after.

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

The three questions:

| ID | Question | Introduced in |
| --- | --- | --- |
| Q1 | Which destination can Galaxium Travels customers visit? | Lab 2 |
| Q2 | Which services does Galaxium Travels offer? | Lab 3 |
| Q3 | Which training does a Lunar Excursions customer need before departure? | Lab 4 (text only), Lab 8 (graph) |

## Prerequisites

Lab 1 lists the tools to install and runs the first start, which downloads the models and packages. Run every command from the repository root. Use only the demo database: Lab 1 deletes it.

## How to read the expected results

- `graphrag inspect`, `ingest` plans and `migrate` plans should match the recorded document revisions and facts with the same files, embedding model name and dimensions (timestamps differ). `graphrag search` always runs retrieval and expansion, but scores and ranking can vary with model artifacts and runtime versions.
- `graphrag ask` uses a local LLM. Its wording varies from run to run. Each lab says what a correct answer must contain and what to look out for.
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
| Lab set | 1.0.0 (this page) | — |

Graph state after each lab (first 12 characters of each revision):

| After lab | Ontology | company-overview | lunar-itinerary | lunar-training-policy |
| --- | --- | --- | --- | --- |
| 1, 2 | 1 | `67b0010436b7` (1 revision) | `4b9e5f32b2f7` (1) | — |
| 3 | 1 | `dda631181ef7` (2) | `4b9e5f32b2f7` (1) | — |
| 4, 5 | 1 | `dda631181ef7` (2) | `4b9e5f32b2f7` (1) | `c605d673f7f5` (1) |
| 6 | 2 | `9ede1e012ffb` (3) | `2e78a4da7fa0` (2) | `506be0ab4d67` (2) |
| 7, 8 | 2 | `9ede1e012ffb` (3) | `2e78a4da7fa0` (2) | `ee18024d91ef` (3) |

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
