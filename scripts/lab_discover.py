# SPDX-License-Identifier: Apache-2.0
"""Lab 11: AI-assisted relationship discovery across documents. Read-only on the graph.

1. Candidate slots are computed deterministically: every (subject, relation, object) that the
   active ontology allows between stored entities and that is not yet a fact.
2. The local LLM judges each slot against ALL stored document texts and must quote evidence.
3. Deterministic gates drop invented slots and quotes that do not appear in the cited document.
4. Survivors are proposals for a human reviewer. With --output, each proposal is also written
   as a curated document that `graphrag ingest` can plan; nothing is imported automatically.
"""
import argparse
import json
import re
from pathlib import Path

from lab_graph import current_documents, store

from local_graphrag.data import validate

DISCOVERY_PROMPT_VERSION = "discovery-v1"
DISCOVERY_PROMPT = """You review a knowledge graph about the fictional company Galaxium Travels.
Decide for each candidate relation whether the documents support it.

Relation meanings:
- OFFERS: the company sells the service.
- VISITS: the service takes customers to the destination.
- REQUIRES: customers must complete the training before taking the service.

Rules:
- supported is true only if a document states the relation or directly implies it.
- Combining documents is allowed, for example a name in one document and its meaning in another.
- quote must be copied character for character from exactly one document; use "" if unsupported.
- document is the id of the document the quote is copied from.
- Answer every candidate exactly once, in the given order. Do not add candidates.

Return JSON only: {"candidates": [{"subject": "...", "relation": "...", "object": "...",
"supported": true, "document": "...", "quote": "...", "reason": "one sentence"}]}

Documents:
%s

Candidates:
%s
"""


def candidate_slots(documents, ontology):
    entities, existing = {}, set()
    for item in documents.values():
        for entity in item["document"]["entities"]:
            entities[entity["id"]] = entity
        existing |= {(f["subject"], f["relation"], f["object"]) for f in item["document"]["facts"]}
    slots = []
    for relation, (left, right) in sorted(ontology["relations"].items()):
        for s in sorted(i for i, e in entities.items() if e["type"] == left):
            for o in sorted(i for i, e in entities.items() if e["type"] == right):
                if s != o and (s, relation, o) not in existing:
                    slots.append((s, relation, o))
    return entities, slots


def ask_model(settings, documents, entities, slots):
    from langchain_ollama import ChatOllama
    corpus = "\n\n".join(f"[{doc_id}]\n{item['document']['text']}" for doc_id, item in documents.items())
    listing = "\n".join(f"- {s} ({entities[s]['name']}) {r} {o} ({entities[o]['name']})" for s, r, o in slots)
    model = ChatOllama(model=settings.chat_model, base_url=settings.ollama, temperature=0, seed=42,
                       format="json", reasoning=False)
    reply = model.invoke(DISCOVERY_PROMPT % (corpus, listing)).content
    reply = re.sub(r"<think>.*?</think>\s*", "", reply, flags=re.DOTALL)
    return json.loads(reply).get("candidates", [])


def gate(answer, slots, documents):
    """Deterministic checks; the model's judgement alone never makes a proposal."""
    key = (answer.get("subject"), answer.get("relation"), answer.get("object"))
    if key not in slots:
        return "rejected: not a candidate slot (invented entity or relation)"
    if answer.get("supported") is not True:
        return "not supported (model)"
    document = documents.get(answer.get("document"))
    if document is None:
        return f"rejected: unknown evidence document {answer.get('document')!r}"
    quote = answer.get("quote") or ""
    if not quote.strip() or quote not in document["document"]["text"]:
        return "rejected: quote does not appear in the cited document"
    return "proposed: needs human review"


def curated_document(answer, entities, documents, ontology):
    """A proposal holding one unreviewed relation, in the normal document format."""
    s, r, o = answer["subject"], answer["relation"], answer["object"]
    evidence = documents[answer["document"]]["document"]
    fact = {"subject": s, "relation": r, "object": o}
    return validate({
        "id": f"discovered-{s}-{r.lower()}-{o}",
        "title": f"Discovered relation: {entities[s]['name']} {r} {entities[o]['name']}",
        "source": evidence["source"],
        "ontology_version": ontology["version"],
        "text": (f"{entities[s]['name']} {r} {entities[o]['name']}. Proposed by the discovery script "
                 f"from the stored documents; not reviewed.\nEvidence from {evidence['id']}: {answer['quote']}"),
        "entities": [entities[s], entities[o]],
        "facts": [fact],
        "evidence": [{**fact, "quote": answer["quote"]}],
    }, ontology)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", help="Write one curated document per proposal into this folder")
    parser.add_argument("--slots-only", action="store_true", help="List the candidate slots; no LLM call")
    args = parser.parse_args()
    graph = store()
    try:
        ontology = graph.active_ontology()
        documents = current_documents(graph)
        settings = graph.settings
    finally:
        graph.close()
    entities, slots = candidate_slots(documents, ontology)
    if args.slots_only:
        print(json.dumps({"ontology": ontology["version"],
                          "slots": [f"{s} {r} {o}" for s, r, o in slots]}, indent=2))
        return
    answers = ask_model(settings, documents, entities, slots)
    results, written = [], []
    for answer in answers:
        status = gate(answer, set(slots), documents)
        row = {"candidate": f"{answer.get('subject')} {answer.get('relation')} {answer.get('object')}",
               "status": status, "document": answer.get("document"), "quote": answer.get("quote"),
               "reason": answer.get("reason")}
        if status.startswith("proposed"):
            declared = {e["id"] for e in documents[answer["document"]]["document"]["entities"]}
            row["cross_document"] = not {answer["subject"], answer["object"]} <= declared
            if args.output:
                document = curated_document(answer, entities, documents, ontology)
                path = Path(args.output) / f"{document['id']}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
                written.append(str(path))
        results.append(row)
    answered = {r["candidate"] for r in results}
    missing = [f"{s} {r} {o}" for s, r, o in slots if f"{s} {r} {o}" not in answered]
    print(json.dumps({"model": settings.chat_model, "prompt_version": DISCOVERY_PROMPT_VERSION,
                      "ontology": ontology["version"], "slots": len(slots), "results": results,
                      "unanswered_slots": missing, "written": written,
                      "graph": "unchanged; review the proposals, then plan them with ./scripts/ingest.sh"},
                     indent=2))


if __name__ == "__main__":
    main()
