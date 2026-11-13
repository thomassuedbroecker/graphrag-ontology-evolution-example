# SPDX-License-Identifier: Apache-2.0
"""Lab 9: check every stored fact against another ontology. Read-only; needs Neo4j only."""
import argparse
import json
import sys

from lab_graph import check_fact, current_documents, fact_label, store

from local_graphrag.data import load_ontology


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", required=True, help="Ontology file to check the stored facts against")
    args = parser.parse_args()
    target = load_ontology(args.ontology)
    graph = store()
    try:
        documents = current_documents(graph)
    finally:
        graph.close()
    valid, invalid = [], []
    for document_id, item in documents.items():
        document = item["document"]
        entities = {e["id"]: e for e in document["entities"]}
        for fact in document["facts"]:
            reason = check_fact(fact, entities, target)
            if reason:
                invalid.append({"fact": fact_label(fact, document_id), "reason": reason})
            else:
                valid.append(fact_label(fact, document_id))
    print(json.dumps({"ontology": target["version"], "valid": sorted(valid),
                      "invalid": sorted(invalid, key=lambda i: i["fact"])}, indent=2))
    sys.exit(1 if invalid else 0)


if __name__ == "__main__":
    main()
