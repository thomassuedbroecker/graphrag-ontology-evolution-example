# Licenses and provenance

This page records what was checked; it is not legal advice.

## Repository

Repository-authored code, documentation, SVG diagrams and sample data: [Apache License 2.0](../LICENSE), with attribution in [NOTICE](../NOTICE). Python and shell files carry an `SPDX-License-Identifier: Apache-2.0` header. Copyright 2026 Thomas Suedbroecker and contributors. External dependencies, applications, container images and model weights keep their own licenses; the repository license does not relicense them. Screenshots show repository data inside a third-party interface; Apache-2.0 does not grant rights to Neo4j branding or interface artwork. Parts of this repository were written with AI assistance.

## Upstream content

Source: [Galaxium Travels watsonx.ai example @ 61e9b4e](https://github.com/thomassuedbroecker/galaxium-travels-graph-rag-watsonx-ai-example/tree/61e9b4e66c404092540af945948d2180b83f5264), Apache-2.0, no NOTICE file at that revision. The local Markdown is byte-identical to upstream blob `6c8a10a9…` (checked with `git hash-object`).

| Local content | Origin |
| --- | --- |
| `data/input-documents/galaxium-travels-company_overview.md` | Upstream `code/langgraph-graph-rag/scripts/input_data/company_overview.md`, renamed |
| `data/scenarios/new-service/` | Upstream overview with Lunar Photography Tours added |
| `data/documents/`, `data/scenarios/new-service/documents/` | Derived from the overview by the local mapping |
| Training policy, candidate, ontologies, diagrams | Original to this repository |
| `images/01-graph.png`, `images/02-graph.png`, `images/03-graph.png`, `images/04-graph.png`, `images/05-graph.png`, `images/06-graph.png` | Original screenshots of Neo4j Browser showing this repository's demo data. The depicted data is this repository's; the Neo4j Browser interface itself is Neo4j's |

## Python dependencies (107 locked packages)

Review on 13 November 2026: regenerated metadata matches the checked-in inventory for all 107 exact locked versions. This confirms declared metadata, not a review of every bundled license or source file.

| License family | Packages |
| --- | --- |
| MIT | 56 |
| BSD (2- and 3-clause) | 25 |
| Apache-2.0 | 16 |
| Dual Apache-2.0 OR MIT/BSD | 4 (`cryptography`, `ormsgpack`, `packaging`, `sniffio`) |
| **MPL-2.0 (weak copyleft)** | 2 (`certifi`, `orjson`; see below) |
| ISC | 2 (`dnspython`, `shellingham`) |
| Unlicense | 1 (`email-validator`) |
| PSF-2.0 | 1 (`typing_extensions`) |
| GPL / AGPL | 0 |

Direct dependencies: FastMCP and the Neo4j driver are Apache-2.0; LangChain, langchain-ollama and langchain-mcp-adapters are MIT; python-dotenv is BSD-3-Clause.

**Points to review before redistributing packages** (using them locally needs no action):

- **MPL-2.0:** `certifi` (MPL-2.0) and `orjson` (`MPL-2.0 AND (Apache-2.0 OR MIT)`). If you ship modified versions of their MPL-covered files, you must provide that source. Unmodified use and bundling are straightforward.
- **Imprecise labels:** `lupa` declares "MIT style" and bundles Lua/LuaJIT (MIT). `charset-normalizer`, `httpx-sse`, `jsonref`, `python-dotenv` and `xxhash` declare only a free-text license field (MIT, MIT, MIT, BSD-3-Clause, BSD-2-Clause), with no SPDX expression or classifier. Check their bundled license files before redistribution.
- Many packages use legacy metadata instead of an SPDX `License-Expression`. The inventory keeps the raw fields.

Full per-package data: [dependency-licenses.json](dependency-licenses.json). Regenerate after dependency changes. The command fails if the environment differs from the lock:

```bash
.venv/bin/python scripts/license_inventory.py > docs/dependency-licenses.json
```

The JSON is a metadata inventory, not an SPDX SBOM.

## Runtime components and model weights

The pinned [upstream license](https://raw.githubusercontent.com/thomassuedbroecker/galaxium-travels-graph-rag-watsonx-ai-example/61e9b4e66c404092540af945948d2180b83f5264/LICENSE), Neo4j license, Ollama license and Qwen model license links were checked during the 13 November 2026 review.

None of these are included in the repository; they are downloaded separately.

| Component | License |
| --- | --- |
| Neo4j Community 5.26.0 | **GPLv3** ([license](https://github.com/neo4j/neo4j/blob/5.26.0/LICENSE.txt)) |
| Ollama 0.40.16 | MIT ([license](https://github.com/ollama/ollama/blob/v0.40.16/LICENSE)) |
| Rancher Desktop | Apache-2.0 ([license](https://github.com/rancher-sandbox/rancher-desktop/blob/main/LICENSE)) |
| `qwen3:8b` weights | Apache-2.0 ([model page](https://ollama.com/library/qwen3:8b)) |
| `nomic-embed-text` (v1.5) weights | Apache-2.0 ([model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)) |

**Neo4j and the GPL:** running Neo4j Community locally and talking to it over Bolt places no GPL obligations on this repository's code. If you **redistribute** the Neo4j image or binaries, the GPLv3 terms apply to them: provide source and keep the notices. The image also contains other components with their own notices.

Model tags can change. Record model IDs with your results ([verification](verification.md)), and review the license of any replacement model. Local inference with permissively licensed weights does not by itself make the setup "Open Source AI".
