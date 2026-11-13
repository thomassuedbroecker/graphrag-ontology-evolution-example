# Fully local Galaxium Travels GraphRAG

A local learning experiment: **LangChain answering agent → FastMCP read-only tools → Neo4j graph and vector retrieval**, with **Ollama** for chat and embeddings. Inference and retrieval use local services; the first setup downloads packages, images and models.

The fictional company data comes from the [original watsonx.ai example](https://github.com/thomassuedbroecker/galaxium-travels-graph-rag-watsonx-ai-example). Repository code, docs, diagrams and sample data are [Apache 2.0](LICENSE); depicted third-party interfaces retain their own rights. See [licenses and provenance](docs/licenses.md).

## What you will learn

This example separates three changes: new facts within an existing ontology, new domain concepts that need an ontology extension, and breaking definitions that the additive migrator refuses. It also separates deterministic graph maintenance from model-dependent answering.

You should be comfortable with Python, JSON and shell commands. Lab 1 lists the local runtime prerequisites; no cloud account or API key is needed.

## Why a graph?

Ask *"Which destination can Galaxium Travels customers visit?"*. The curated graph represents the answer across two documents:

- `company-overview` says Galaxium Travels **OFFERS** Lunar Excursions.
- `lunar-itinerary` says Lunar Excursions **VISITS** the Moon.

Vector search finds passages; the graph hop through the shared `lunar-excursions` entity connects their facts. The passage text also mentions the Moon, so a correct answer alone does not prove graph use. In the recorded runs, the model skipped graph expansion and added unsupported destinations ([experiment results](docs/results.md)). The labs also show how to **maintain** that graph when sources change: which data the insertion rules accept, why some data fits when it should not, and how to change the graph definition and migrate existing data.

![Answering reads through MCP; maintenance validates before writing; Ollama embeds both.](docs/architecture-assets/overview.svg)

## Reading paths

- **Blog companion:** read this overview, [ontology vs data model](docs/graphs/ontology-vs-data-model.md), then [recorded results](docs/results.md).
- **Hands-on learner:** Labs 1–8 cover the main story. Labs 9–12 are optional extensions; run them in order after Lab 8.
- **AI engineer:** focus on tool traces, evidence quality, discovery proposals and evaluation in the [developer guide](docs/development.md).
- **Developer:** follow [architecture](docs/architecture.md), the code links and [runtime reference](docs/reference.md).

## Labs

Start with [Lab 1: initial setup](labs/01-initial-setup.md), then follow the [lab catalog](labs/README.md) for commands, expected results and graph versions.

- **Core story (Labs 1–8):** build the baseline, add a service, encounter a training requirement that needs a new ontology, migrate, and compare answers.
- **Optional experiments (Labs 9–12):** reject a breaking change, inspect its impact, review AI-proposed relationships, and run regression checks.

Data enters the graph only through `graphrag ingest` and `graphrag migrate`, which enforce fixed [insertion rules](labs/README.md#rules-for-inserting-data-into-the-graph). Free-form JSON is rejected.

## Limitations

- **Curated baseline.** `graphrag prepare` maps one known Markdown section with reviewed rules. Lab 11 separately asks an LLM to propose relations between existing entities; an operator reviews and imports them.
- **Validation checks structure, not truth.**
- **Tool use is prompted, not enforced.** See [Lab 2](labs/02-initial-question.md).
- **Read-only is a code boundary.** MCP and the importer share one Neo4j credential.
- **Migration is additive only.** Removed or redefined types and relations need a rebuild; there is no down-migration.
- **Not implemented:** document deletion, unattended relationship discovery/import, persisted approvals, chunking of large documents, concurrent importers.
- **Local, not air-gapped.** `start.sh --offline` refuses downloads, but this is not an audited air gap.

## Documentation

| If you want to… | Read |
| --- | --- |
| Learn step by step | [Labs](labs/README.md) |
| See how the data changes in each step | [Data lineage](docs/data-lineage.md) |
| Understand the graph, ontology and storage | [Graph versions](docs/graphs/README.md) |
| See components and design decisions | [Architecture](docs/architecture.md) |
| Change code, prompts or models | [Developer and AI engineer guide](docs/development.md) |
| Configure or troubleshoot | [Runtime reference](docs/reference.md) |
| Reproduce measurements | [Experiment results](docs/results.md) |
| Check licenses | [Licenses and provenance](docs/licenses.md) |

`./scripts/test.sh` runs 31 local tests and skips the service test; `./scripts/test.sh --services` also runs that rerunnable integration test against the running Neo4j and Ollama.
