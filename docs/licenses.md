# Licenses and provenance

The repository, downloaded software and model weights have separate licenses.

## Repository

Repository-authored code, documentation, SVG diagrams and sample data: [Apache License 2.0](../LICENSE), with attribution in [NOTICE](../NOTICE). External dependencies, applications, container images and model weights keep their own licenses; the repository license does not relicense them. Screenshots show repository data inside a third-party interface; Apache-2.0 does not grant rights to Neo4j branding or interface artwork. Parts of this repository were written with AI assistance.

## Upstream content

Source: [Galaxium Travels watsonx.ai example @ 61e9b4e](https://github.com/thomassuedbroecker/galaxium-travels-graph-rag-watsonx-ai-example/tree/61e9b4e66c404092540af945948d2180b83f5264), Apache-2.0. The source file is preserved in the path below.

| Local content | Origin |
| --- | --- |
| `data/input-documents/galaxium-travels-company_overview.md` | Upstream `code/langgraph-graph-rag/scripts/input_data/company_overview.md`, renamed |
| `data/scenarios/new-service/` | Upstream overview with Lunar Photography Tours added |
| `data/documents/`, `data/scenarios/new-service/documents/` | Derived from the overview by the local mapping |
| Training policy, candidate, ontologies, diagrams, breaking-change and regression fixtures | Created for this repository |
| Relationship-discovery fixture | Derived from the new-service text and stored entities; the demo interpretation and review limits are explained in [Lab 11](../labs/11-ai-assisted-relationship-discovery.md) |
| `images/02-graph.png`, `images/03-graph.png`, `images/04-graph.png`, `images/05-graph.png`, `images/06-graph.png` | Original screenshots of Neo4j Browser showing this repository's demo data. The depicted data is this repository's; the Neo4j Browser interface itself is Neo4j's |

## Python dependencies (107 locked packages)

The [inventory](dependency-licenses.json) lists declared license metadata for each exact version in `requirements.lock`. It is metadata, not a review of every bundled source or license file.

Direct dependencies: FastMCP and the Neo4j driver are Apache-2.0; LangChain, langchain-ollama and langchain-mcp-adapters are MIT; python-dotenv is BSD-3-Clause.

**Points to review before redistributing packages:**

- **MPL-2.0:** `certifi` (MPL-2.0) and `orjson` (`MPL-2.0 AND (Apache-2.0 OR MIT)`). Redistributing MPL-covered files, including unmodified binaries, requires retaining notices and making the covered source available under the MPL. See the [Mozilla MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).
- **Imprecise labels:** `lupa` declares "MIT style" and bundles Lua/LuaJIT (MIT). `charset-normalizer`, `httpx-sse`, `jsonref`, `python-dotenv` and `xxhash` declare only a free-text license field (MIT, MIT, MIT, BSD-3-Clause, BSD-2-Clause), with no SPDX expression or classifier. Check their bundled license files before redistribution.
- Many packages use legacy metadata instead of an SPDX `License-Expression`. The inventory keeps the raw fields.

Full per-package data: [dependency-licenses.json](dependency-licenses.json). Regenerate after dependency changes. The command fails if the environment differs from the lock:

```bash
.venv/bin/python scripts/license_inventory.py > docs/dependency-licenses.json
```

The JSON is a metadata inventory, not an SPDX SBOM.

## Runtime components and model weights

None of these are included in the repository; they are downloaded separately.

| Component | License |
| --- | --- |
| Neo4j Community 5.26.0 | **GPLv3** ([license](https://github.com/neo4j/neo4j/blob/5.26.0/LICENSE.txt)) |
| Ollama 0.40.16 | MIT ([license](https://github.com/ollama/ollama/blob/v0.40.16/LICENSE)) |
| Rancher Desktop 1.24.0 | Apache-2.0 ([license](https://github.com/rancher-sandbox/rancher-desktop/blob/v1.24.0/LICENSE)) |
| `qwen3:8b` weights | Apache-2.0 ([model page](https://ollama.com/library/qwen3:8b)) |
| `nomic-embed-text` (v1.5) weights | Apache-2.0 ([model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)) |

**Neo4j and the GPL:** running Neo4j Community locally and talking to it over Bolt places no GPL obligations on this repository's code. If you **redistribute** the Neo4j image or binaries, the GPLv3 terms apply to them: provide source and keep the notices. The image also contains other components with their own notices.

Model tags can change. Record model IDs with your results ([experiment results](results.md)), and review the license of any replacement model. Local inference with permissively licensed weights does not by itself make the setup "Open Source AI".
