# Lab 2: Initial data and initial question

[← Lab 1](01-initial-setup.md) · [Labs](README.md) · Next: [Lab 3](03-add-fitting-data.md)

**Goal:** ask Q1 and see why it needs the graph. Compare the evidence that is *available* with the evidence the agent *uses*.

| | Before | After |
| --- | --- | --- |
| Ontology | 1 | 1 (read-only lab) |
| Facts | 4 | 4 |

**Q1:** *Which destination can Galaxium Travels customers visit?*

No single passage answers Q1. `company-overview` says Galaxium **OFFERS** Lunar Excursions. `lunar-itinerary` says Lunar Excursions **VISITS** the Moon. The answer needs both facts.

## Step 1: Retrieval only (no LLM)

```bash
.venv/bin/graphrag search "Which destination can Galaxium Travels customers visit?"
```

**Expected result** (summarised: document, score, graph facts reached from it):

```text
company-overview 0.858
    Galaxium Travels OFFERS Lunar Excursions [company-overview]
    Galaxium Travels OFFERS Orbital Flights [company-overview]
    Galaxium Travels OFFERS Space Hotel Stays [company-overview]
    Lunar Excursions VISITS Moon [lunar-itinerary]
lunar-itinerary 0.851
    Galaxium Travels OFFERS Lunar Excursions [company-overview]
    Lunar Excursions VISITS Moon [lunar-itinerary]
```

Look at the first block. The company passage reaches `Lunar Excursions VISITS Moon`, a fact **owned by another document**. That hop through the shared `lunar-excursions` entity is the graph part of GraphRAG.

## Step 2: Ask the agent

```bash
.venv/bin/graphrag ask --trace "Which destination can Galaxium Travels customers visit? Cite your sources."
```

**Expected result:**

- A correct answer names **the Moon** and cites `lunar-itinerary` (`galaxium:company-overview#lunar-excursions`).
- Recorded run: `"tool_calls": [{"tool": "search_documents", …}]`. **No `graph_context` call.** The answer named the Moon, but also listed "lunar orbit" as a destination. That comes from the passage text, not from the graph.

```text
Galaxium Travels customers can visit the **Moon** and **lunar orbit** as destinations.
1. Moon Surface Exploration … (document_id: lunar-itinerary) …
```

## What you learned

| Evidence | Available? | Used by the agent? |
| --- | --- | --- |
| Passages (vector search) | Yes | Yes |
| `Lunar Excursions VISITS Moon` (graph) | Yes | No, in the recorded run |

Only `Moon` is a `Destination` in the graph. Anything else the agent calls a destination is the model's interpretation of the text. The [AI engineer guide](../docs/development.md#for-ai-engineers) covers how to measure and close this gap.

## Check yourself

- [ ] `search` shows the cross-document fact under `company-overview`.
- [ ] You can tell from `--trace` whether the agent called `graph_context`.
