# Experiment results

Retrieval can find the right facts while the answering model still skips the graph. Compare the tool trace with the answer, not just whether the answer mentions the Moon.

## Recorded run (13 November 2026)

Environment: Apple M4 Max, 36 GB, macOS 27.0.1, Python 3.14.2, Ollama 0.40.16, `qwen3:8b` (`500a1f067a9f`), `nomic-embed-text` (`0a109f422b47`), Neo4j image `sha256:5a015e53de18…`, langchain 1.3.18, langchain-ollama 1.1.0, langchain-mcp-adapters 0.2.2, fastmcp 2.14.7, neo4j driver 5.28.8. Prompt `answering-v1`.

**Retrieval** for *"Which destination can Galaxium Travels customers visit?"*:

| Document | Score | Graph facts returned |
| --- | --- | --- |
| `company-overview` | 0.858 | 3 × OFFERS, plus `Lunar Excursions VISITS Moon` (owned by `lunar-itinerary`) |
| `lunar-itinerary` | 0.851 | `Galaxium OFFERS Lunar Excursions`, `Lunar Excursions VISITS Moon` |

The cross-document hop works as designed.

**Agent**, three runs. Runs 1–2 predate the separate `#lunar-excursions` source anchor and the missing-evidence check:

| Run | Tool calls | Answer |
| --- | --- | --- |
| 1 (`ask --trace`) | `search_documents` (limit 5) | Moon via Lunar Excursions, cited `lunar-itinerary` ✓; also listed "orbital space stations" and "orbital space hotels" as destinations ✗ |
| 2 (`verify_runtime.py`) | `search_documents` (limit 5) | Listed the three *services* as destinations, cited only `company-overview` ✗ |
| 3 (`verify_runtime.py`) | `search_documents` (`"destinations"`, limit 5) | Moon, cited `lunar-itinerary` with `#lunar-excursions` ✓; also listed "lunar orbit" as a destination ✗ |
| 3, absence question | `search_documents` (limit 5) | "The provided documents do not mention any specific training requirements" ✓ |

No run called `graph_context`. Only Moon is a `Destination` in the graph, so the extra "destinations" are unsupported. Answers varied between runs despite temperature 0. One answer took about 24 s.

**What this teaches:** deterministic retrieval reaches the cross-document fact, but prompting alone does not ensure the agent uses it. A citation and a correct keyword can coexist with unsupported claims. Next steps are in the [AI engineer guide](development.md#what-the-recorded-run-shows).

## Repeat the checks

```bash
./scripts/start.sh
./scripts/test.sh --services
.venv/bin/python scripts/verify_runtime.py
```

The service test modifies documents and restores the baseline at the end. Run it only against the demo database. It can be rerun; `./scripts/stop.sh --delete-data` gives a completely fresh database.

`verify_runtime.py` writes a JSON report to `.runtime/verification/` (ignored by Git). It includes versions, model IDs, `doctor`, retrieval, a traced answer and a traced absence-question answer. It exits nonzero if any check fails. Read the answer yourself as well: the checks are smoke tests, not a grounding evaluation.
