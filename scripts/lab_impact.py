# SPDX-License-Identifier: Apache-2.0
"""Lab 10: ontology impact analysis before a migration. Read-only; never writes to the graph.

Reports which entities, facts, documents and questions a target ontology would affect.
Exit code 0: no stored fact or entity is invalid under the target and the target removes or changes
no definition. Exit code 1: impact found, or the change is breaking even where no stored fact uses it.
The `migration` field repeats the importer's own verdict; it is never an approval.
"""
import argparse
import json
import re
import sys

from lab_graph import ROOT, check_fact, current_documents, fact_label, repair_hint, store

from local_graphrag.data import check_migration, load_ontology, ontology_diff


def code_references(names):
    """Hard-coded uses of affected relation names in the application code (src/)."""
    hits = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(re.search(rf"\b{re.escape(name)}\b", line) for name in names):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    return hits


def migration_verdict(current, target):
    """What `graphrag migrate` would say about this target, using the importer's own checks."""
    try:
        check_migration(current, target)
    except ValueError as error:
        return f"refused by graphrag migrate: {error}"
    return "accepted by graphrag migrate's checks; still needs review before --apply"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ontology", required=True, help="Target ontology file (not applied)")
    parser.add_argument("--questions", default=str(ROOT / "data/scenarios/regression/questions.json"))
    parser.add_argument("--no-questions", action="store_true",
                        help="Skip the question check (no Ollama embedding calls)")
    args = parser.parse_args()
    target = load_ontology(args.ontology)
    graph = store()
    try:
        current = graph.active_ontology()
        documents = current_documents(graph)
        diff = ontology_diff(current, target)

        # Facts: every stored fact, checked against the target.
        names, facts, invalid = {}, [], {}
        for document_id, item in documents.items():
            entities = {e["id"]: e for e in item["document"]["entities"]}
            names.update({e["id"]: e["name"] for e in entities.values()})
            for fact in item["document"]["facts"]:
                reason = check_fact(fact, entities, target)
                row = {"fact": fact_label(fact, document_id), "status": "invalid" if reason else "valid"}
                if reason:
                    row.update(reason=reason, repair=repair_hint(fact, entities, current, target))
                    invalid[(fact["subject"], fact["relation"], fact["object"], document_id)] = row
                facts.append(row)

        # Entities: removed types, plus endpoints of invalid facts.
        affected_entities = {}
        for document_id, item in documents.items():
            for entity in item["document"]["entities"]:
                if entity["type"] not in target["entity_types"]:
                    affected_entities[entity["id"]] = f"type {entity['type']} removed"
        for subject, relation, obj, _ in invalid:
            for entity_id in (subject, obj):
                affected_entities.setdefault(entity_id, f"endpoint of an invalid {relation} fact")

        # Documents: owners must be re-extracted; documents that only mention affected
        # entities keep their own facts, but their graph context (retrieval expansion) changes.
        report_documents = []
        for document_id, item in documents.items():
            document = item["document"]
            owned = sorted(row["fact"] for key, row in invalid.items() if key[3] == document_id)
            mentions = sorted(e["id"] for e in document["entities"] if e["id"] in affected_entities)
            action = ("re-extract or rebuild" if owned else
                      "review answers: graph context changes" if mentions else "none")
            report_documents.append({"id": document_id, "revision": item["revision"],
                                     "invalid_facts": owned, "mentions_affected": mentions,
                                     "action": action})

        # Questions: which affected facts each question's retrieval would hand to the model.
        report_questions = []
        if not args.no_questions:
            invalid_by_name = {(names[s], r, names[o], d): row["fact"] for (s, r, o, d), row in invalid.items()}
            catalog = json.loads(open(args.questions, encoding="utf-8").read())["questions"]
            for entry in catalog:
                hits = graph.search(entry["question"])
                seen = set()
                for hit in hits:
                    for row in graph.context(hit["document_id"]):
                        key = (row["subject"], row["relation"], row["object"], row["document_id"])
                        if key in invalid_by_name:
                            seen.add(invalid_by_name[key])
                report_questions.append({
                    "id": entry["id"], "question": entry["question"],
                    "retrieved": [f"{h['document_id']} {h['score']:.3f}" for h in hits],
                    "affected_facts": sorted(seen)})
    finally:
        graph.close()

    touched = sorted(set(diff["removed_relations"]) | set(diff["changed_relations"]))
    summary = {
        "documents": len(documents),
        "documents_to_re_extract": sum(1 for d in report_documents if d["invalid_facts"]),
        "documents_with_changed_context": sum(1 for d in report_documents
                                              if not d["invalid_facts"] and d["mentions_affected"]),
        "facts": len(facts), "facts_invalid": len(invalid),
        "entities_affected": len(affected_entities),
        "questions_affected": sum(1 for q in report_questions if q["affected_facts"]),
    }
    report = {
        "from": current["version"], "to": target["version"], "diff": diff, "summary": summary,
        "facts": facts,
        "entities": [{"id": key, "reason": value} for key, value in sorted(affected_entities.items())],
        "documents": report_documents,
        "questions": report_questions if not args.no_questions else "skipped (--no-questions)",
        "code_references": code_references(touched),
        "migration": migration_verdict(current, target),
    }
    print(json.dumps(report, indent=2))
    sys.exit(1 if invalid or affected_entities or not diff["compatible"] else 0)


if __name__ == "__main__":
    main()
