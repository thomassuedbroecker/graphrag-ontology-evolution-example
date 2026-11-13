# Reading the Neo4j screenshots

The screenshots record Labs 1–7. Use the [ontology diagrams](README.md) for concepts and `graphrag inspect` for exact facts: Neo4j Browser truncates labels and can overlap edges.

## Nodes and edges

| Visible element | Meaning |
| --- | --- |
| Blue `Entity` | Company, service, destination or training; inspect `type` |
| Orange `Document` | Current passage, source and embedding |
| Purple `Revision` | Retained JSON snapshot; inspect `hash` |
| Red `Ontology` | Versioned graph definition; inspect `active` |
| `MENTIONS` | Document refers to an entity; retrieval expansion starts here |
| `RELATION` | Domain fact; inspect `kind` (OFFERS, VISITS, REQUIRES) and owning `document_id` |
| `HAS_REVISION` | Document has a retained snapshot; not necessarily the current one |
| `EXTENDS` | Ontology v2 extends v1 |

Colors and positions are display settings. A document and an entity can have similar captions; check their Neo4j labels and full IDs.

## Changes through the labs

The remaining screenshots are embedded beside their commands in the labs, so this guide links to those explanations.

| State | What to notice | Walkthrough |
| --- | --- | --- |
| Baseline (`02-graph.png`) | Five entities, two documents, four facts, isolated v1 ontology | [Lab 1](../../labs/01-initial-setup.md) |
| New service (`03-graph.png`) | Photography Tours adds one Service and one OFFERS; only company content changes | [Lab 3](../../labs/03-add-fitting-data.md) |
| Passage only (`04-graph.png`) | Training policy adds a document mentioning Lunar Excursions, with no Training entity or REQUIRES fact | [Lab 4](../../labs/04-add-non-fitting-data.md) |
| Migration (`05-graph.png`) | v2 becomes active and extends v1; each document gains a revision; five facts remain | [Lab 6](../../labs/06-migrate-graph-data.md) |
| Training fact (`06-graph.png`) | Training entity and REQUIRES appear; six facts, three training-policy revisions | [Lab 7](../../labs/07-add-new-data.md) |

## Verify the properties behind the drawing

Run the read-only queries in the [runtime reference](../reference.md#inspecting-the-graph).

`HAS_REVISION` alone does not identify the current snapshot: its `hash` must match `Document.hash`. Reimporting previously seen content reuses the existing snapshot. Retrieval uses current document passages and active facts, not old snapshots. Disconnected entities can remain after a document replacement and provide no current evidence.
