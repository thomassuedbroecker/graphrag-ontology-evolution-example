# Lab 12: Validation and regression

[← Lab 11](11-ai-assisted-relationship-discovery.md) · [Labs](README.md)

**Goal:** compare the graph built step by step in Labs 1–11 with a **full rebuild from the sources** and with a **reviewed ground truth**, and see that the comparison catches a regression.

| | Before | After |
| --- | --- | --- |
| Graph | Built incrementally (Labs 1–11) | Rebuilt from sources |
| Active ontology | 2 | 2 |
| Facts | 7 | 7 (identical) |
| Current revisions | 4 documents | Identical |
| Revision history | 3 / 1 / 2 / 3 revisions | 3 / 1 / 2 / **1** (shorter) |

This lab **deletes the demo database** in Step 5.

## The ground truth

[ground-truth.json](../data/scenarios/regression/ground-truth.json) is the reviewed expected state after Lab 11:

| Part | Content | Why it can be exact |
| --- | --- | --- |
| `ontology` | `2` | — |
| `documents` | Current revision of each of the 4 documents | Revisions are SHA-256 of document + embedding model + dimensions, so they are content-addressed |
| `facts`, `entity_types` | 7 facts with owning document; type counts | Deterministic |
| `questions` | Per question: expected top document, required graph facts, required answer terms | Retrieval is checked strictly; answers are checked by terms only |
| `rebuild` | The recipe: which sources rebuild this state | Lets the ground truth be **re-derived**, not just believed |

It does **not** contain revision counts, timestamps or scores. Those depend on history and runtime, not on content.

[lab_regression.py](../scripts/lab_regression.py) compares a state with the ground truth. It never writes to the graph. Exit code 0 means every check passed.

## Step 1: Verify the ground truth itself (offline)

```bash
.venv/bin/python scripts/lab_regression.py --offline
```

**Expected result:** exit code 0, `"compared_with": "rebuild from sources (in memory)"`, `"passed": true`, and four checks (`ontology`, `documents`, `facts`, `entity_types`) with no differences.

No services are involved. The script replays the `rebuild` recipe in memory: `prepare` the [new-service source](../data/scenarios/new-service/company-overview.md) for v2, then load the [training candidate](../data/scenarios/training-requirement/candidates/training.json) and the [reviewed discovery](../data/scenarios/relationship-discovery/reviewed). It then computes the revision hashes. A match shows that the expected content is reproducible from these files. It checks reproducibility, not whether the source assumptions are true.

## Step 2: Check the incrementally built graph

```bash
.venv/bin/python scripts/lab_regression.py
```

**Expected result:** exit code 0 and nine passed checks:

| Check | Result |
| --- | --- |
| `ontology`, `documents`, `facts`, `entity_types`, `embedding` | No differences |
| `retrieval Q1` | top `company-overview`; both `VISITS Moon` facts in context |
| `retrieval Q2` | top `company-overview`; all four `OFFERS` facts |
| `retrieval Q3` | top `lunar-training-policy`; `REQUIRES` fact |
| `retrieval Q4` | top `company-overview`; both `VISITS Moon` facts |

A passing comparison means your current content matches the reference state.

## Step 3: Introduce a regression

A typical mistake: someone re-maps the **original** company overview (without Lunar Photography Tours) for v2 and imports it.

```bash
.venv/bin/graphrag prepare --ontology data/ontologies/v2.json --output .runtime/lab-12/stale
./scripts/ingest.sh --data .runtime/lab-12/stale
```

**Expected result:** the plan already warns you:

```json
[
  { "id": "company-overview", "action": "update", "added_facts": [],
    "removed_facts": ["galaxium OFFERS lunar-photography-tours"] },
  { "id": "lunar-itinerary", "action": "unchanged", "added_facts": [], "removed_facts": [] }
]
```

Apply it anyway, then check:

```bash
./scripts/ingest.sh --data .runtime/lab-12/stale --apply
.venv/bin/python scripts/lab_regression.py
```

**Expected result:** exit code 1 and:

```json
"passed": false,
"failed": ["documents", "facts", "retrieval Q2"],
{ "check": "documents", "differences": { "company-overview": { "expected": "9ede1e012ffb", "actual": "777862b4b447" } } },
{ "check": "facts", "missing": ["galaxium OFFERS lunar-photography-tours  [company-overview]"], "unexpected": [] },
{ "check": "retrieval Q2", "missing_graph_facts": ["Galaxium Travels OFFERS Lunar Photography Tours"] }
```

Look at what **passed**:

- `entity_types` still has `Service: 4`. The discovered document from Lab 11 still mentions Lunar Photography Tours, so the entity survives.
- `retrieval Q4` passes: *Lunar Photography Tours VISITS Moon* is still there.

The graph now says a service visits the Moon that the company **no longer offers**. Each document is valid on its own, but together they are inconsistent. Only a comparison against an expected **whole** state finds this.

## Step 4: Why not just fix it in place?

You could re-import the right source (Lab 3) and the check would pass again. A full rebuild proves more: that the current state can be produced **only from the sources and reviewed files**, without the history of manual steps.

## Step 5: Full rebuild

```bash
./scripts/stop.sh --delete-data && ./scripts/start.sh            # fresh graph, v1 baseline
.venv/bin/graphrag migrate --ontology data/ontologies/v2.json --apply
.venv/bin/graphrag prepare --source data/scenarios/new-service/company-overview.md \
  --ontology data/ontologies/v2.json --output .runtime/lab-12/rebuild
cp data/scenarios/training-requirement/candidates/training.json \
   data/scenarios/relationship-discovery/reviewed/*.json .runtime/lab-12/rebuild/
./scripts/ingest.sh --data .runtime/lab-12/rebuild               # plan
./scripts/ingest.sh --data .runtime/lab-12/rebuild --apply
```

The replay starts at v1 because `start.sh` always imports the v1 baseline into an empty graph. An empty graph counts as v1.

**Expected result:** the migration moves `company-overview` `67b0010436b7` → `777862b4b447` and `lunar-itinerary` `4b9e5f32b2f7` → `2e78a4da7fa0`. The plan then shows:

```json
[
  { "id": "company-overview", "action": "update", "added_facts": ["galaxium OFFERS lunar-photography-tours"], "removed_facts": [] },
  { "id": "discovered-lunar-photography-tours-visits-moon", "action": "create", "added_facts": ["lunar-photography-tours VISITS moon"], "removed_facts": [] },
  { "id": "lunar-itinerary", "action": "unchanged", "added_facts": [], "removed_facts": [] },
  { "id": "lunar-training-policy", "action": "create", "added_facts": ["lunar-excursions REQUIRES lunar-surface-safety"], "removed_facts": [] }
]
```

All four documents go in **one** apply, which is a single atomic write.

## Step 6: Compare the rebuild with the ground truth

```bash
.venv/bin/python scripts/lab_regression.py --answers
.venv/bin/graphrag inspect
```

`--answers` also asks all four questions through the agent and checks the required terms, which takes a few minutes.

**Recorded result** (model outputs may differ): exit code 0, `"passed": true`, 13 checks: the nine from Step 2 plus `answer Q1`–`answer Q4`. Recorded answers: Q1 *Moon* (via Lunar Excursions and Lunar Photography Tours), Q2 the four services, Q3 *Lunar Surface Safety training*, Q4 *Lunar Excursions* and *Lunar Photography Tours*.

`inspect` shows the same revisions and facts as after Lab 11. Only the history differs:

| Document | Revision | Revisions after Lab 11 | Revisions after rebuild |
| --- | --- | --- | --- |
| company-overview | `9ede1e012ffb` | 3 (v1 → v1 + new service → v2) | 3 (v1 → v2 → v2 + new service) |
| discovered-… | `0c4b479b4a38` | 1 | 1 |
| lunar-itinerary | `2e78a4da7fa0` | 2 | 2 |
| lunar-training-policy | `ee18024d91ef` | 3 (passage v1 → v2 → modelled) | **1** (created as modelled) |

Same content, different paths. `company-overview` reached the same revision in a different order. The training policy lost its passage-only history, because that history is not in the sources. The ground truth deliberately ignores history.

## What the three comparisons prove

| Comparison | Proves | Catches |
| --- | --- | --- |
| Ground truth ↔ sources (`--offline`) | The expectation matches the listed sources and curated files | Reference/source drift (coordinated errors can still pass) |
| Ground truth ↔ incremental graph | The step-by-step path did not lose or invent anything | Regressions like Step 3 |
| Ground truth ↔ rebuild | The state needs no manual history | Facts that exist only because of a manual step |

`--answers` is the weakest check: the LLM's wording varies, so it only tests required terms. Retrieval and facts are the reliable regression signal. The answer is a smoke test.

## Check yourself

- [ ] `--offline` passed without any services.
- [ ] The stale import failed `documents`, `facts` and `retrieval Q2`, but **not** `retrieval Q4`. You can explain why.
- [ ] After the rebuild every check passed, and `lunar-training-policy` has 1 revision instead of 3.

<details>
<summary><b>Show answers</b></summary>

1. Offline matching shows the sources reproduce the reference content; it does not prove the assumptions true.
2. The stale company import removes OFFERS, affecting documents, facts and Q2. The separate discovery document keeps VISITS, so Q4 still passes.
3. The rebuild has the same current content but no passage-only training history. The reference deliberately ignores history.

</details>

Start over: [Reset](README.md#reset).
