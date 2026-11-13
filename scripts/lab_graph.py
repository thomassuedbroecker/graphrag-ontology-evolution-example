# SPDX-License-Identifier: Apache-2.0
"""Shared, read-only helpers for Labs 9-12. Nothing in this module writes to the graph."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def store():
    """Open the repository's Store with the settings from .env (Neo4j and Ollama must be running)."""
    from local_graphrag.config import Settings
    from local_graphrag.store import Store
    return Store(Settings.load())


def current_documents(graph):
    """Return the current revision snapshot of every stored document, keyed by document ID."""
    rows = graph.query("MATCH (d:Document)-[:HAS_REVISION]->(v:Revision) WHERE v.hash = d.hash "
                       "RETURN d.id AS id, d.hash AS hash, v.snapshot AS snapshot ORDER BY id")
    return {row["id"]: {"revision": row["hash"][:12], "document": json.loads(row["snapshot"])}
            for row in rows}


def fact_label(fact, document_id):
    return f"{fact['subject']} {fact['relation']} {fact['object']}  [{document_id}]"


def check_fact(fact, entities, ontology):
    """Explain why one stored fact is invalid under `ontology`, or return None if it is valid."""
    types = set(ontology["entity_types"])
    subject, obj = entities[fact["subject"]], entities[fact["object"]]
    for entity in (subject, obj):
        if entity["type"] not in types:
            return f"entity type {entity['type']} removed ({entity['id']})"
    relation = ontology["relations"].get(fact["relation"])
    if relation is None:
        return f"relation {fact['relation']} removed"
    if tuple(relation) != (subject["type"], obj["type"]):
        return (f"{fact['relation']} now connects {relation[0]} -> {relation[1]}; "
                f"this fact connects {subject['type']} -> {obj['type']}")
    return None


def repair_hint(fact, entities, current, target):
    """Classify how an invalid fact could be repaired. A hint for the reviewer, never applied."""
    pair = [entities[fact["subject"]]["type"], entities[fact["object"]]["type"]]
    if fact["relation"] not in target["relations"]:
        renamed = [name for name, ends in target["relations"].items()
                   if ends == pair and name not in current["relations"]]
        if renamed:
            return f"mechanical: rename to {renamed[0]} (same endpoints; needs approval)"
        return "remove or re-model: no relation in the target fits these endpoints"
    return "re-extract from the source: the relation's meaning changed"
