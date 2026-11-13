# SPDX-License-Identifier: Apache-2.0
"""Versioned, curated ontology; no LLM participates in validation or writes."""
import hashlib
import json
import re
from pathlib import Path

# Single source of truth for the active importer ontology (editable install from the repo).
V1_PATH = Path(__file__).resolve().parents[2] / "data" / "ontologies" / "v1.json"


def load_ontology(path):
    """Load a validation specification, not permission to migrate the database."""
    ontology = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(ontology.get("version"), str) or not ontology["version"].strip():
        raise ValueError("Ontology requires a version")
    if ontology.get("status") not in {"baseline", "proposed", "approved"}:
        raise ValueError("Ontology status must be baseline, proposed or approved")
    if "extends" in ontology and not isinstance(ontology["extends"], str):
        raise ValueError("Ontology extends must be a version string")
    types = ontology.get("entity_types")
    if not isinstance(types, list) or not types or not all(isinstance(t, str) and t.strip() for t in types):
        raise ValueError("Ontology requires entity types")
    if len(types) != len(set(types)):
        raise ValueError("Duplicate ontology entity types")
    relations = ontology.get("relations")
    if not isinstance(relations, dict) or not relations:
        raise ValueError("Ontology requires relations")
    for name, pair in relations.items():
        if not name.strip() or not isinstance(pair, list) or len(pair) != 2 or not all(
            isinstance(t, str) and t in types for t in pair
        ):
            raise ValueError("Ontology relation endpoints must reference declared types")
    return ontology


V1 = load_ontology(V1_PATH)
if V1["status"] != "baseline":
    raise ValueError("The importer ontology must have status baseline")
ONTOLOGY_VERSION = V1["version"]
ENTITY_TYPES = set(V1["entity_types"])
RELATIONS = {k: tuple(v) for k, v in V1["relations"].items()}


# Insertion rules, part 1: the document format. Only these fields can reach the graph;
# anything else (free-form JSON, extra properties, nested payloads) is rejected, not ignored.
DOCUMENT_FIELDS = {"required": {"id", "title", "text", "source", "ontology_version", "entities", "facts"},
                   "optional": {"source_version", "evidence"}}
ITEM_FIELDS = {"Entity": {"id", "name", "type"}, "Fact": {"subject", "relation", "object"},
               "Evidence": {"subject", "relation", "object", "quote"}}
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _fields(item, allowed, what, required=None):
    if not isinstance(item, dict):
        raise ValueError(f"{what} must be a JSON object")
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise ValueError(f"{what} has fields outside the document format: {unknown}")
    missing = sorted((required or allowed) - set(item))
    if missing:
        raise ValueError(f"{what} is missing required fields: {missing}")


def _strings(item, keys, what):
    if not isinstance(item, dict):
        raise ValueError(f"{what} must be a JSON object")
    for key in keys:
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError(f"{what} requires a non-empty string {key!r}")


def validate(document, ontology=None):
    ontology = ontology or V1
    version, types = ontology["version"], set(ontology["entity_types"])
    relations = {k: tuple(v) for k, v in ontology["relations"].items()}
    _fields(document, DOCUMENT_FIELDS["required"] | DOCUMENT_FIELDS["optional"], "Document",
            DOCUMENT_FIELDS["required"])
    _strings(document, ("id", "title", "text", "source"), "Document")
    if not SLUG.fullmatch(document["id"]):
        raise ValueError(f"Document id must be a lowercase slug: {document['id']!r}")
    if document["text"].lstrip()[:1] in ("{", "["):
        raise ValueError(f"Document {document['id']} text must be a prose passage, not embedded JSON")
    if document.get("ontology_version") != version:
        raise ValueError(f"Unsupported ontology version: document declares "
                         f"{document.get('ontology_version')!r}, ontology is {version!r}")
    for key in ("entities", "facts"):
        if not isinstance(document.get(key), list):
            raise ValueError(f"Document {document['id']} requires a list {key!r}")
    entities = {}
    for entity in document["entities"]:
        _fields(entity, ITEM_FIELDS["Entity"], "Entity")
        _strings(entity, ("id", "name", "type"), "Entity")
        if not SLUG.fullmatch(entity["id"]):
            raise ValueError(f"Entity id must be a lowercase slug: {entity['id']!r}")
        if entity["type"] not in types:
            raise ValueError(f"Unknown entity type: {entity['type']}")
        if entity["id"] in entities:
            raise ValueError("Duplicate entity ID")
        entities[entity["id"]] = entity
    seen = set()
    for fact in document["facts"]:
        _fields(fact, ITEM_FIELDS["Fact"], "Fact")
        _strings(fact, ("subject", "relation", "object"), "Fact")
        signature = (fact["subject"], fact["relation"], fact["object"])
        if signature in seen:
            raise ValueError("Duplicate fact")
        seen.add(signature)
        if signature[0] not in entities or signature[2] not in entities:
            raise ValueError("Fact references an undeclared entity")
        pair = (entities[signature[0]]["type"], entities[signature[2]]["type"])
        if relations.get(signature[1]) != pair:
            raise ValueError(f"Invalid ontology relation: {signature}")
    source_version = document.get("source_version")
    if source_version is not None and not (
        isinstance(source_version, str) and re.fullmatch(r"[0-9a-f]{64}", source_version)
    ):
        raise ValueError("source_version must be a lowercase SHA-256 hex digest")
    # Optional per-fact evidence: each quote must back a declared fact and appear in the passage.
    evidence = document.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("Document evidence must be a list")
    for item in evidence:
        _fields(item, ITEM_FIELDS["Evidence"], "Evidence")
        _strings(item, ("subject", "relation", "object", "quote"), "Evidence")
        if (item["subject"], item["relation"], item["object"]) not in seen:
            raise ValueError("Evidence references an undeclared fact")
        if item["quote"] not in document["text"]:
            raise ValueError("Evidence quote does not appear in the document text")
    return document


def load_documents(directory, ontology=None):
    docs = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            docs.append(validate(json.loads(path.read_text(encoding="utf-8")), ontology))
        except ValueError as error:  # includes json.JSONDecodeError
            raise ValueError(f"{path}: {error}") from error
    if not docs:
        raise ValueError(f"No JSON documents in {directory}")
    if len({d["id"] for d in docs}) != len(docs):
        raise ValueError("Duplicate document ID")
    entities = {}
    for doc in docs:
        for entity in doc["entities"]:
            if entity["id"] in entities and entities[entity["id"]] != entity:
                raise ValueError(f"Conflicting shared entity: {entity['id']}")
            entities[entity["id"]] = entity
    return docs


def ontology_diff(old, new):
    """Compare two graph definitions. Compatible means additive: nothing removed or redefined."""
    old_types, new_types = set(old["entity_types"]), set(new["entity_types"])
    old_rel = {k: list(v) for k, v in old["relations"].items()}
    new_rel = {k: list(v) for k, v in new["relations"].items()}
    changed = {k: {"from": old_rel[k], "to": new_rel[k]}
               for k in sorted(old_rel.keys() & new_rel.keys()) if old_rel[k] != new_rel[k]}
    removed_types, removed_rel = sorted(old_types - new_types), sorted(old_rel.keys() - new_rel.keys())
    return {
        "from": old["version"], "to": new["version"],
        "added_types": sorted(new_types - old_types), "removed_types": removed_types,
        "added_relations": {k: new_rel[k] for k in sorted(new_rel.keys() - old_rel.keys())},
        "removed_relations": removed_rel, "changed_relations": changed,
        "unchanged_relations": sorted(k for k in old_rel.keys() & new_rel.keys() if k not in changed),
        "compatible": not (removed_types or removed_rel or changed),
    }


def check_migration(current, target):
    """Only additive, approved successors of the active version may be migrated to."""
    if target["version"] == current["version"]:
        raise ValueError(f"Graph is already on ontology {current['version']}")
    if target["status"] != "approved":
        raise ValueError(f"Ontology {target['version']} is {target['status']}, not approved")
    if target.get("extends") != current["version"]:
        raise ValueError(f"Ontology {target['version']} extends {target.get('extends')!r}, "
                         f"but the graph is on {current['version']!r}")
    diff = ontology_diff(current, target)
    if not diff["compatible"]:
        raise ValueError("Only additive migrations are supported; removed or changed definitions need a rebuild")
    return diff


def migrate_document(document, target):
    """Relabel a stored document to the target version and prove it is still valid there."""
    return validate({**document, "ontology_version": target["version"]}, target)


def fingerprint(document, model, dimensions):
    payload = {"document": document, "embedding_model": model, "dimensions": dimensions}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
