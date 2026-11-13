# Lab 8: The initial question, the new question and the newest question

[← Lab 7](07-add-new-data.md) · [Labs](README.md)

**Goal:** ask all three questions against the final graph and compare with the earlier labs.

| | State |
| --- | --- |
| Ontology | 2 |
| Documents | `company-overview@9ede1e012ffb`, `lunar-itinerary@2e78a4da7fa0`, `lunar-training-policy@ee18024d91ef` |
| Facts | 6 |

## Q1 (initial question): Which destination can Galaxium Travels customers visit?

```bash
.venv/bin/graphrag search "Which destination can Galaxium Travels customers visit?"
.venv/bin/graphrag ask --trace "Which destination can Galaxium Travels customers visit? Cite your sources."
```

**Expected result:** `search` returns `company-overview` 0.859, `lunar-itinerary` 0.851, `lunar-training-policy` 0.749. Each reaches `Lunar Excursions VISITS Moon [lunar-itinerary]`. The correct answer is still **the Moon**: no lab added a `VISITS` fact.

Recorded answer: Moon (surface and orbit), plus "orbital destinations" from Orbital Flights and Space Hotel Stays. Those are **not** `Destination` entities in the graph. The model again called only `search_documents`.

## Q2 (new question from Lab 3): Which services does Galaxium Travels offer?

```bash
.venv/bin/graphrag search "Which services does Galaxium Travels offer?"
.venv/bin/graphrag ask --trace "Which services does Galaxium Travels offer? Cite your sources."
```

**Expected result:** `search` returns `company-overview` 0.894 with four `OFFERS` facts. The answer lists **Orbital Flights, Lunar Excursions, Space Hotel Stays, Lunar Photography Tours**, citing `galaxium:company-overview#primary-services`. The recorded run matched exactly.

## Q3 (newest question): Which training does a Lunar Excursions customer need before departure?

```bash
.venv/bin/graphrag search "Which training does a Lunar Excursions customer need before departure?"
.venv/bin/graphrag ask --trace "Which training does a Lunar Excursions customer need before departure? Cite your sources."
```

**Expected result:**

```text
lunar-training-policy 0.928
    Galaxium Travels OFFERS Lunar Excursions [company-overview]
    Lunar Excursions VISITS Moon [lunar-itinerary]
    Lunar Excursions REQUIRES Lunar Surface Safety [lunar-training-policy]
company-overview 0.842
    … 4 × OFFERS, VISITS Moon,
    Lunar Excursions REQUIRES Lunar Surface Safety [lunar-training-policy]
lunar-itinerary 0.837
    … OFFERS, VISITS Moon,
    Lunar Excursions REQUIRES Lunar Surface Safety [lunar-training-policy]
```

Recorded answer: *Lunar Excursions requires completion of **Lunar Surface Safety training** before departure*, citing `lunar-training-policy` (`galaxium:lunar-training-policy`).

## Compare Lab 4 with Lab 8

The Q3 answer text is the same in both labs. The graph is not:

| | Lab 4 (v1, passage only) | Lab 8 (v2, modelled) |
| --- | --- | --- |
| `REQUIRES` fact | None | `lunar-excursions REQUIRES lunar-surface-safety` |
| Reached from `company-overview` | No | Yes, through the shared `lunar-excursions` entity |
| Reached from `lunar-itinerary` (the Moon) | No | Yes |
| Question *"What must I complete before visiting the Moon?"* | Only if vector search happens to rank the policy passage | Graph path: Moon ← VISITS ← Lunar Excursions → REQUIRES → Lunar Surface Safety |

The new fact is now available **from every document that mentions Lunar Excursions**. That is the point of modelling the dependency instead of leaving it in text.

## Summary of all labs

| Lab | Ontology | Facts | What changed |
| --- | --- | --- | --- |
| 1 | 1 | 4 | Baseline imported |
| 2 | 1 | 4 | — (questions only) |
| 3 | 1 | 5 | `+ galaxium OFFERS lunar-photography-tours` |
| 4 | 1 | 5 | `lunar-training-policy` passage; dependency rejected or text-only |
| 5 | 1 | 5 | v2 definition compared, approved, not active |
| 6 | 2 | 5 | All documents migrated; facts unchanged |
| 7 | 2 | 6 | `+ lunar-excursions REQUIRES lunar-surface-safety` |
| 8 | 2 | 6 | — (questions only) |

## Check yourself

- [ ] Q1 and Q2 answers are unchanged from Lab 3.
- [ ] `REQUIRES` appears under all three documents in the Q3 `search`.
- [ ] Note whether your agent called `graph_context` this time. If it did not, the graph evidence was available but unused (see Lab 2).

Start over: [Reset](README.md#reset).
