# Developer and AI engineer guide

Start with [Lab 1](../labs/01-initial-setup.md) and the [architecture](architecture.md).

## Where to change what

| Task | Code | Checks |
| --- | --- | --- |
| Map source Markdown to passages and facts | [prepare.py](../src/local_graphrag/prepare.py) | [test_prepare.py](../tests/test_prepare.py) |
| Change the ontology or validation rules | [v1.json](../data/ontologies/v1.json), [data.py](../src/local_graphrag/data.py) | [test_data.py](../tests/test_data.py), [test_architecture_data.py](../tests/test_architecture_data.py) |
| Change import, revisions, retrieval or graph expansion | [store.py](../src/local_graphrag/store.py) | [test_services.py](../tests/test_services.py) (`--services`) |
| Change MCP tools | [server.py](../src/local_graphrag/server.py) | [test_mcp.py](../tests/test_mcp.py) |
| Change the answering prompt or agent | [prompts.py](../src/local_graphrag/prompts.py), [agent.py](../src/local_graphrag/agent.py) | [test_agent.py](../tests/test_agent.py), [verify_runtime.py](../scripts/verify_runtime.py) |
| Add commands or settings | [cli.py](../src/local_graphrag/cli.py), [config.py](../src/local_graphrag/config.py) | CLI help, smoke run |
| Change service lifecycle | [scripts](../scripts), [compose.yaml](../compose.yaml) | [test_scripts.py](../tests/test_scripts.py) |

Run `./scripts/test.sh` after every change. Use `./scripts/test.sh --services` when you touch `store.py`; it is rerunnable and leaves the baseline imported. The CLI is the supported write path. `Store.apply` also revalidates against the graph's active ontology. The service test needs a graph on v1: after Lab 6, reset with `./scripts/stop.sh --delete-data && ./scripts/start.sh`, otherwise it is skipped.

`v1.json` defines the baseline and the default for offline validation. `data.py` loads it at import time; imports use the active definition stored in Neo4j, which becomes v2 after migration. This requires the editable install that `setup.sh` performs.

## Trace one question

*"Which destination can Galaxium Travels customers visit?"*

1. `ask.sh` → `cli.py` → `agent.ask`.
2. The agent discovers the two MCP tools; the chat model decides which to call.
3. `search_documents` → `Store.search`: Ollama embeds the question; Neo4j's `document_embeddings` cosine index returns passages with `document_id` and `source`.
4. `graph_context("company-overview")` follows MENTIONS to `lunar-excursions` and returns the adjacent `VISITS → Moon` fact owned by `lunar-itinerary`.
5. The intended answer is "the Moon", citing `lunar-itinerary` and `galaxium:company-overview#lunar-excursions`.

The [data lineage](data-lineage.md) shows the real payload at each step.

Step 4 is where the measured run diverges (see below).

## For AI engineers

### Inspect what the agent did

```bash
.venv/bin/graphrag ask --trace "Which destination can Galaxium Travels customers visit?"
```

This prints JSON with `model`, `prompt_version`, the ordered `tool_calls` with arguments, and the `answer`. Compare it with `graphrag search`, which runs retrieval and graph expansion deterministically without the LLM. If `search` contains the evidence and the answer does not, the problem is tool use or synthesis, not retrieval.

### What the model sees

The model's context is the system prompt ([prompts.py](../src/local_graphrag/prompts.py)), the question, and the two tool schemas. Their docstrings in [server.py](../src/local_graphrag/server.py) **are** prompt text:

| Tool | Description the model reads | Arguments |
| --- | --- | --- |
| `search_documents` | "Find local source passages by semantic similarity. Returns source IDs for citation." | `question: str`, `limit: int = 3` (1–10) |
| `graph_context` | "Find facts connected to a retrieved document's entities, including other documents." | `document_id: str` |

Each tool result is appended to the conversation as JSON. A `search_documents` row carries `document_id`, `title`, `source`, the **whole passage** `text` and `score`; a `graph_context` row carries `subject`, `relation`, `object`, `document_id` and `source`. Real examples: [data lineage, steps 6–8](data-lineage.md#6-search-question--passages).

`RECURSION_LIMIT = 16` in [agent.py](../src/local_graphrag/agent.py) caps model turns plus tool calls; `ANSWER_TIMEOUT_SECONDS` caps wall time.

### What the recorded run shows

With `qwen3:8b` and prompt `answering-v1`, the model called only `search_documents` and never `graph_context`, so it never saw the typed `VISITS → Moon` fact as a graph fact. It answered from passage text and listed unsupported "destinations" (hotels, space stations, lunar orbit). Details: [verification](verification.md#recorded-run-13-november-2026).

**Likely root cause:** the search result already looks sufficient. The `lunar-itinerary` passage contains "Moon surface exploration", and the company passage contains the full service list, so the model has little reason to make a second call. It then reads every place-like phrase in the text as a destination, because only the graph knows that `Moon` is the one `Destination`. Options to try, each measured separately:

- **Prompt revision.** Copy the prompt to a new version in [prompts.py](../src/local_graphrag/prompts.py) (e.g. `answering-v2`) that requires `graph_context` before answering about relationships, and says that only graph facts establish entity types such as Destination.
- **Tool description.** Make the `graph_context` docstring state *when* to call it ("call for every retrieved document before answering questions about relationships or types").
- **Deterministic chain.** Always run search → expand in code and give the model only the combined evidence. More reliable, less agentic.
- **Another model.** Tool-calling quality differs by model; see below.

### Prompt versioning

The prompt lives in [prompts.py](../src/local_graphrag/prompts.py) with `ANSWERING_PROMPT_VERSION`. Change the version string whenever the text changes. `--trace` and `verify_runtime.py` record it, so results stay comparable.

### Evaluating answers

`scripts/verify_runtime.py` is a small evaluation harness. It checks:

| Check | Meaning |
| --- | --- |
| `retrieved_lunar_fact` | Retrieval plus graph expansion returns `VISITS → Moon` from `lunar-itinerary` |
| `agent_searched_then_expanded_graph` | The agent called `search_documents` and then `graph_context` |
| `answer_has_expected_citation` | The answer mentions Moon, `lunar-itinerary` and `galaxium:company-overview#lunar-excursions` |
| `answer_reports_missing_evidence` | Asked which training Lunar Excursions requires (no such data in v1), the answer says the evidence is missing (phrase heuristic) |

It uses the question shown in the README, so results stay comparable. These are smoke checks. Citation presence does not prove grounding, so still read the answer. To evaluate more broadly, add question/expected-evidence pairs, run each several times (answers vary even at temperature 0), and report pass rates per model and prompt version.

### Choosing models

- **Chat model** (`OLLAMA_CHAT_MODEL`): must support tool calling in Ollama. Smaller models answer faster but follow multi-step tool instructions less reliably. After switching, run `verify_runtime.py` and compare `tool_calls`. Reasoning models may emit `<think>` blocks; `agent.py` strips them from the answer.
- **Embedding model** (`OLLAMA_EMBED_MODEL`, `EMBEDDING_DIMENSIONS`): changing either requires a fresh database (`./scripts/stop.sh --delete-data`) and full reimport, because the vector index has fixed dimensions.
- Raise `ANSWER_TIMEOUT_SECONDS` for slow hardware or large models.
- Check the license of any replacement model ([licenses](licenses.md#runtime-components-and-model-weights)).

## Changing the data

Keep entity IDs stable. A new service name must be added to the `SERVICES` mapping in `prepare.py`; that is not an ontology change. Run `ingest.sh` without `--apply` first and check `added_facts` and `removed_facts` before writing. A new entity type or relation needs a new ontology JSON (`status`, `extends`), an `ontology-diff` review and a `migrate`. Validating against a file does not activate it. New document fields need a change to `DOCUMENT_FIELDS` in `data.py`; never store unvalidated JSON.

## Diagrams

SVGs in [architecture-assets](architecture-assets) and [graphs/assets](graphs/assets) are hand-written sources: 720 px wide, 20–26 px text, short labels, dashed outlines for additions (see each diagram legend). Edit them as text and preview them before committing. Keep them in step with the code.

## Possible extensions

The labs cover deterministic preparation, operator-reviewed updates and additive migration. Further experiments, in priority order:

1. Measure agent graph use and unsupported claims across Q1–Q3, several runs and prompt/model versions; compare with a fixed search → expand chain.
2. Give MCP a separate read-only database credential.
3. Persist maintenance diffs and review decisions bound to source hashes before commit.
4. Evaluate versioned LLM extraction against the curated facts, with evidence per assertion and explicit entity resolution. Route parser failures to mapping review and unsupported claims to evidence review; neither alone justifies an ontology change.
5. Add migration simulation, consumer/query regression checks and recovery for non-additive changes. Compare incremental updates with a rebuild by correctness, time, tokens and review effort.
