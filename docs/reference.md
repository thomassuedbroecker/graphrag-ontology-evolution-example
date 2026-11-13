# Runtime reference

Run commands from the repository root.

## Configuration

`setup.sh` creates `.env` from [.env.example](../.env.example). Environment variables override `.env`.

| Setting | Default | Notes |
| --- | --- | --- |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Must be loopback |
| `NEO4J_USERNAME` | `neo4j` | |
| `NEO4J_PASSWORD` | demo value in `.env.example` | Applied only when the Neo4j volume is first created |
| `NEO4J_DATABASE` | `neo4j` | |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Plain HTTP loopback origin, no path |
| `OLLAMA_CHAT_MODEL` | `qwen3:8b` | Must support tool calling |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Changing it requires a fresh database |
| `EMBEDDING_DIMENSIONS` | `768` | Must match the embedding model |
| `MCP_URL` | `http://127.0.0.1:8000/mcp` | Server binds to this host, port and path |
| `ANSWER_TIMEOUT_SECONDS` | `300` | `ask` fails instead of hanging |

`LANGSMITH_TRACING=false` and `ANONYMIZED_TELEMETRY=false` keep the run local. Restart MCP (`stop.sh` then `start.sh`) after changing settings; a running MCP process is reused without reloading. On v1, restarting also reapplies the baseline company and lunar documents; see the [lab reset notes](../labs/README.md#reset).

Docker: the scripts use the `rancher-desktop` context if it exists, unless `DOCKER_CONTEXT` or `DOCKER_HOST` is set. `PYTHON_BIN=python3.12 ./scripts/setup.sh` picks the interpreter for a new `.venv`.

## Commands

| Command | Purpose |
| --- | --- |
| `./scripts/start.sh [--offline]` | Set up, start Ollama/Neo4j/MCP, import `data/documents`, run `doctor` |
| `./scripts/status.sh` | Show service state |
| `./scripts/stop.sh [--delete-data]` | Stop services; `--delete-data` also deletes the Neo4j volume |
| `./scripts/ingest.sh [--data DIR] [--apply]` | Plan, or with `--apply` write, an import |
| `./scripts/ask.sh "question"` | Ask the agent |
| `graphrag prepare [--source MD] [--output DIR] [--ontology JSON]` | Markdown → JSON; no services needed |
| `graphrag validate [--data DIR] [--ontology JSON]` | Validate offline |
| `graphrag ontology-diff OLD NEW` | Compare two graph definitions; no services needed |
| `graphrag migrate --ontology JSON [--apply]` | Plan, or with `--apply` run, an additive ontology migration |
| `graphrag inspect` | Active ontology, document revisions, facts |
| `graphrag search "question"` | Retrieval + graph expansion without the LLM |
| `graphrag ask --trace "question"` | Answer with tool calls and prompt version |
| `graphrag doctor` | Check Neo4j, models and MCP discovery |

## Troubleshooting

- Logs: `.runtime/mcp.log`, `.runtime/ollama.log`, and `docker compose logs`. Failed starts leave services running for diagnosis.
- `Another lifecycle command is active`: after an interrupted start, remove the empty `.runtime/start.lock` directory once you've confirmed no script is running.
- `Port … is occupied`: another process holds the Ollama or MCP port; stop it or change the URL.
- Changing `NEO4J_PASSWORD` after the first start has no effect; use `stop.sh --delete-data` to start over.

## Inspecting the graph

Run these read-only queries in Neo4j Browser. They rely on properties, not on colors or layout. Expected results per scenario: [graph screenshots](graphs/initial-and-update.md#verify-the-properties-behind-the-drawing).

```cypher
// Active facts and the document that owns each one
MATCH (s:Entity)-[r:RELATION]->(o:Entity)
RETURN s.name AS subject, r.kind AS relation, o.name AS object,
       r.document_id AS document_id, r.source AS source
ORDER BY document_id, subject, relation, object;

// Which entities each document mentions (starting points for graph_context)
MATCH (d:Document)-[:MENTIONS]->(e:Entity)
RETURN d.id AS document_id, e.id AS entity_id, e.name AS entity
ORDER BY document_id, entity_id;

// Revision history; true marks the snapshot of the active version
MATCH (d:Document)-[:HAS_REVISION]->(v:Revision)
RETURN d.id AS document_id, v.id AS revision_id, v.created_at AS created_at,
       v.hash = d.hash AS matches_active_document
ORDER BY document_id, created_at;
```

Removed files do not delete documents, and entities with no remaining facts stay in the graph. Revisions are snapshots, not an event log.

## Offline operation and reproducibility

After one successful online start, `./scripts/start.sh --offline` skips Python installs, refuses model pulls and sets Compose to `--pull never`. New Ollama processes get `OLLAMA_NO_CLOUD=1`; an Ollama you started yourself keeps its own settings.

`requirements.lock` pins Python packages; Neo4j is pinned to `5.26.0-community`. Model tags can change: record `ollama list` IDs, the Neo4j image digest and hardware with results. `scripts/verify_runtime.py` captures most of this.
