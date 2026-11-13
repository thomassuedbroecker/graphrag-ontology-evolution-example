# SPDX-License-Identifier: Apache-2.0
"""Lab 12: compare a graph state with the reviewed ground truth. Never writes to the graph.

--offline  rebuild the expected state in memory from the source files (no services needed)
(default)  read the live graph: ontology, current revisions, facts, entity types, retrieval
--answers  additionally ask every question through the agent (needs MCP and the chat model)
Exit code 0: every check passed. Exit code 1: at least one check failed.
"""
import argparse
import asyncio
import json
import sys

from lab_graph import ROOT, current_documents, fact_label, store

from local_graphrag.data import fingerprint, load_documents, load_ontology


def expected_from_sources(truth):
    """Replay the rebuild recipe in memory. Revisions are content hashes, so they are reproducible."""
    from local_graphrag.prepare import prepare_documents
    ontology = load_ontology(ROOT / truth["ontology"]["file"])
    documents = {}
    for step in truth["rebuild"]:
        batch = (prepare_documents(ROOT / step["prepare"], ontology) if "prepare" in step
                 else load_documents(ROOT / step["documents"], ontology))
        documents.update({d["id"]: d for d in batch})
    model, dimensions = truth["embedding"]["model"], truth["embedding"]["dimensions"]
    entities = {}
    for document in documents.values():
        entities.update({e["id"]: e["type"] for e in document["entities"]})
    types = {}
    for entity_type in entities.values():
        types[entity_type] = types.get(entity_type, 0) + 1
    return {
        "ontology": ontology["version"],
        "documents": {i: fingerprint(d, model, dimensions)[:12] for i, d in documents.items()},
        "facts": sorted(fact_label(f, i) for i, d in documents.items() for f in d["facts"]),
        "entity_types": dict(sorted(types.items())),
    }


def actual_from_graph(graph):
    state = graph.inspect()
    return {
        "ontology": state["ontology"],
        "documents": {i: item["revision"] for i, item in current_documents(graph).items()},
        "facts": state["facts"],
        "entity_types": state["entity_types"],
        "embedding": {"model": graph.settings.embed_model, "dimensions": graph.settings.dimensions},
    }


def compare(name, expected, actual):
    if isinstance(expected, list):
        missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
        return {"check": name, "passed": not (missing or extra), "missing": missing, "unexpected": extra}
    if isinstance(expected, dict):
        keys = sorted(set(expected) | set(actual))
        diffs = {k: {"expected": expected.get(k), "actual": actual.get(k)}
                 for k in keys if expected.get(k) != actual.get(k)}
        return {"check": name, "passed": not diffs, "differences": diffs}
    return {"check": name, "passed": expected == actual, "expected": expected, "actual": actual}


def retrieval_checks(graph, truth, catalog):
    checks = []
    for expected in truth["questions"]:
        question = catalog[expected["id"]]
        hits = graph.search(question)
        facts = {f"{r['subject']} {r['relation']} {r['object']}"
                 for hit in hits for r in graph.context(hit["document_id"])}
        top = hits[0]["document_id"] if hits else None
        missing = [f for f in expected["graph_facts"] if f not in facts]
        checks.append({"check": f"retrieval {expected['id']}", "passed": top == expected["top_document"] and not missing,
                       "top_document": top, "expected_top": expected["top_document"],
                       "missing_graph_facts": missing})
    return checks


def answer_checks(graph, truth, catalog):
    from local_graphrag.agent import ask
    checks = []
    for expected in truth["questions"]:
        answer = asyncio.run(ask(graph.settings, catalog[expected["id"]] + " Cite your sources."))
        missing = [t for t in expected["answer_terms"] if t.lower() not in answer.lower()]
        checks.append({"check": f"answer {expected['id']}", "passed": not missing,
                       "missing_terms": missing, "answer": answer})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", default=str(ROOT / "data/scenarios/regression/ground-truth.json"))
    parser.add_argument("--questions", default=str(ROOT / "data/scenarios/regression/questions.json"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--answers", action="store_true")
    args = parser.parse_args()
    truth = json.loads(open(args.truth, encoding="utf-8").read())
    catalog = {q["id"]: q["question"] for q in
               json.loads(open(args.questions, encoding="utf-8").read())["questions"]}
    checks = []
    if args.offline:
        actual, against = expected_from_sources(truth), "rebuild from sources (in memory)"
    else:
        graph = store()
        try:
            actual, against = actual_from_graph(graph), "live graph"
            checks.append(compare("embedding", truth["embedding"], actual["embedding"]))
            checks += retrieval_checks(graph, truth, catalog)
            if args.answers:
                checks += answer_checks(graph, truth, catalog)
        finally:
            graph.close()
    checks[0:0] = [compare("ontology", truth["ontology"]["version"], actual["ontology"]),
                   compare("documents", truth["documents"], actual["documents"]),
                   compare("facts", truth["facts"], actual["facts"]),
                   compare("entity_types", truth["entity_types"], actual["entity_types"])]
    failed = [c["check"] for c in checks if not c["passed"]]
    print(json.dumps({"ground_truth": truth["version"], "compared_with": against,
                      "passed": not failed, "failed": failed, "checks": checks}, indent=2))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
