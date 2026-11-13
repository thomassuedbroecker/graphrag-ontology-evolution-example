# SPDX-License-Identifier: Apache-2.0
import json
import math
from datetime import datetime, timezone

from langchain_ollama import OllamaEmbeddings
from neo4j import GraphDatabase

from .data import V1, check_migration, fingerprint, migrate_document, validate


class Store:
    def __init__(self, settings):
        self.settings = settings
        self.driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))
        self.embeddings = OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama)

    def close(self):
        self.driver.close()

    def query(self, cypher, **params):
        records, _, _ = self.driver.execute_query(
            cypher, parameters_=params, database_=self.settings.database
        )
        return [r.data() for r in records]

    def schema(self):
        for label in ("Document", "Entity", "Revision", "Ontology"):
            self.query(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                       f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
        self.query(
            "CREATE VECTOR INDEX document_embeddings IF NOT EXISTS "
            "FOR (d:Document) ON (d.embedding) OPTIONS {indexConfig: {"
            "`vector.dimensions`: $dimensions, `vector.similarity_function`: 'cosine'}}",
            dimensions=self.settings.dimensions,
        )
        self.query("CALL db.awaitIndexes(120)")

    def vector(self, text):
        vector = self.embeddings.embed_query(text)
        if len(vector) != self.settings.dimensions or not all(math.isfinite(x) for x in vector):
            raise ValueError("Embedding dimensions or values do not match configuration")
        return vector

    def plan(self, documents):
        """Per document: create/update/unchanged plus the facts an apply would add or remove."""
        existing = {r["id"]: r["hash"] for r in self.query(
            "MATCH (d:Document) RETURN d.id AS id, d.hash AS hash"
        )}
        stored = {}
        for row in self.query("MATCH (s:Entity)-[r:RELATION]->(o:Entity) "
                              "RETURN r.document_id AS doc, s.id AS s, r.kind AS rel, o.id AS o"):
            stored.setdefault(row["doc"], set()).add(f"{row['s']} {row['rel']} {row['o']}")
        plan = []
        for d in documents:
            digest = fingerprint(d, self.settings.embed_model, self.settings.dimensions)
            action = ("unchanged" if existing.get(d["id"]) == digest
                      else "update" if d["id"] in existing else "create")
            before = stored.get(d["id"], set())
            after = {f"{f['subject']} {f['relation']} {f['object']}" for f in d["facts"]}
            plan.append({"id": d["id"], "action": action,
                         "added_facts": sorted(after - before),
                         "removed_facts": sorted(before - after)})
        return plan

    def active_ontology(self):
        """The graph records which definition it follows; a graph without a record is on v1."""
        rows = self.query("MATCH (o:Ontology {active: true}) RETURN o.definition AS definition")
        if len(rows) > 1:
            raise ValueError("More than one active ontology in the graph")
        return json.loads(rows[0]["definition"]) if rows else V1

    def apply(self, documents):
        active = self.active_ontology()
        for doc in documents:  # The importer follows the graph's ontology, not the file's label.
            validate(doc, active)
        # Compute every embedding before the single atomic data transaction.
        plan = self.plan(documents)
        changed = {item["id"] for item in plan if item["action"] != "unchanged"}
        prepared = [(d, self.vector(d["text"])) for d in documents if d["id"] in changed]
        with self.driver.session(database=self.settings.database) as session:
            session.execute_write(self._write, prepared)
            session.execute_write(self._record_ontology, active)
        return plan

    @staticmethod
    def _record_ontology(tx, ontology):
        tx.run("OPTIONAL MATCH (o:Ontology) WITH count(o) AS n WHERE n = 0 "
               "CREATE (:Ontology {id: $id, definition: $definition, active: true, activated_at: $now})",
               id=ontology["version"], definition=json.dumps(ontology, sort_keys=True),
               now=datetime.now(timezone.utc).isoformat()).consume()

    def inspect(self):
        """Deterministic view of the graph state: versions, revisions and facts."""
        return {
            "ontology": self.active_ontology()["version"],
            "ontology_history": self.query(
                "MATCH (o:Ontology) RETURN o.id AS version, o.active AS active, "
                "o.activated_at AS activated_at ORDER BY o.activated_at"),
            "documents": self.query(
                "MATCH (d:Document)-[:HAS_REVISION]->(v:Revision) "
                "RETURN d.id AS id, d.ontology_version AS ontology_version, "
                "left(d.hash, 12) AS revision, count(v) AS revisions ORDER BY id"),
            "facts": [r["fact"] for r in self.query(
                "MATCH (s:Entity)-[r:RELATION]->(o:Entity) "
                "RETURN s.id + ' ' + r.kind + ' ' + o.id + '  [' + r.document_id + ']' AS fact "
                "ORDER BY fact")],
            "entity_types": {r["type"]: r["count"] for r in self.query(
                "MATCH (e:Entity) RETURN e.type AS type, count(e) AS count ORDER BY type")},
        }

    def _migration(self, target):
        current = self.active_ontology()
        diff = check_migration(current, target)
        rows = self.query("MATCH (d:Document) OPTIONAL MATCH (d)-[:HAS_REVISION]->(v:Revision) "
                          "WHERE v.hash = d.hash RETURN d.id AS id, d.hash AS hash, "
                          "v.snapshot AS snapshot ORDER BY id")
        documents = []
        for row in rows:
            if row["snapshot"] is None:
                raise ValueError(f"Document {row['id']} has no current revision snapshot")
            try:
                migrated = migrate_document(json.loads(row["snapshot"]), target)
            except ValueError as error:
                raise ValueError(f"Document {row['id']} is invalid under {target['version']}: {error}")
            documents.append((row["hash"], migrated,
                              fingerprint(migrated, self.settings.embed_model, self.settings.dimensions)))
        facts = sum(len(doc["facts"]) for _, doc, _ in documents)
        plan = {"from": current["version"], "to": target["version"], "diff": diff,
                "documents": [{"id": doc["id"], "revision_before": before[:12], "revision_after": after[:12]}
                              for before, doc, after in documents],
                "facts_before": facts, "facts_after": facts,
                "embeddings": "reused: text is unchanged"}
        return current, plan, documents

    def migration_plan(self, target):
        return self._migration(target)[1]

    def migrate(self, target):
        """Relabel every current document and switch the active ontology in one transaction."""
        current, plan, documents = self._migration(target)
        with self.driver.session(database=self.settings.database) as session:
            session.execute_write(self._write_migration, current, target, documents)
        return {**plan, "applied": True}

    @staticmethod
    def _write_migration(tx, current, target, documents):
        now = datetime.now(timezone.utc).isoformat()
        tx.run("MERGE (o:Ontology {id: $id}) ON CREATE SET o.definition=$definition, "
               "o.active=true, o.activated_at=$now", id=current["version"],
               definition=json.dumps(current, sort_keys=True), now=now).consume()
        if tx.run("MATCH (o:Ontology {active: true}) RETURN o.id AS id").single()["id"] != current["version"]:
            raise ValueError("The active ontology changed during migration; plan again")
        for before, doc, after in documents:
            tx.run("MATCH (d:Document {id: $id}) WHERE d.hash = $before "
                   "SET d.ontology_version=$version, d.hash=$after "
                   "MERGE (v:Revision {id: $revision}) ON CREATE SET v.hash=$after, "
                   "v.snapshot=$snapshot, v.created_at=$now, v.migrated_from=$before "
                   "MERGE (d)-[:HAS_REVISION]->(v)",
                   id=doc["id"], before=before, after=after, version=target["version"],
                   revision=f"{doc['id']}:{after}", snapshot=json.dumps(doc, sort_keys=True),
                   now=now).consume()
            tx.run("MATCH ()-[r:RELATION {document_id: $id}]->() SET r.revision=$after",
                   id=doc["id"], after=after).consume()
        tx.run("MATCH (old:Ontology {id: $old}) SET old.active=false "
               "MERGE (new:Ontology {id: $new}) SET new.definition=$definition, new.active=true, "
               "new.activated_at=$now MERGE (new)-[:EXTENDS]->(old)",
               old=current["version"], new=target["version"],
               definition=json.dumps(target, sort_keys=True), now=now).consume()

    def _write(self, tx, prepared):
        for doc, vector in prepared:
            digest = fingerprint(doc, self.settings.embed_model, self.settings.dimensions)
            # Reject conflicting entity definitions across imports instead of silently renaming.
            for entity in doc["entities"]:
                result = tx.run("MATCH (e:Entity {id: $id}) RETURN e.name AS name, e.type AS type",
                                id=entity["id"]).single()
                if result and (result["name"], result["type"]) != (entity["name"], entity["type"]):
                    raise ValueError(f"Entity definition conflict: {entity['id']}")
            tx.run("MATCH ()-[r:RELATION {document_id: $id}]->() DELETE r", id=doc["id"]).consume()
            tx.run("MATCH (d:Document {id: $id})-[r:MENTIONS]->() DELETE r", id=doc["id"]).consume()
            tx.run(
                "MERGE (d:Document {id: $id}) SET d.title=$title, d.text=$text, "
                "d.source=$source, d.hash=$hash, d.embedding=$vector, d.embedding_model=$model, "
                "d.ontology_version=$ontology "
                "MERGE (v:Revision {id: $revision}) "
                "ON CREATE SET v.hash=$hash, v.snapshot=$snapshot, v.created_at=$now "
                "MERGE (d)-[:HAS_REVISION]->(v)",
                id=doc["id"], title=doc["title"], text=doc["text"], source=doc["source"],
                hash=digest, vector=vector, model=self.settings.embed_model,
                ontology=doc["ontology_version"], revision=f"{doc['id']}:{digest}",
                snapshot=json.dumps(doc, sort_keys=True),
                now=datetime.now(timezone.utc).isoformat(),
            ).consume()
            for entity in doc["entities"]:
                tx.run("MATCH (d:Document {id: $doc}) MERGE (e:Entity {id: $id}) "
                       "SET e.name=$name, e.type=$type MERGE (d)-[:MENTIONS]->(e)",
                       doc=doc["id"], **entity).consume()
            for fact in doc["facts"]:
                tx.run("MATCH (s:Entity {id: $subject}), (o:Entity {id: $object}) "
                       "MERGE (s)-[r:RELATION {document_id: $doc, kind: $relation}]->(o) "
                       "SET r.source=$source, r.revision=$revision",
                       **fact, doc=doc["id"], source=doc["source"], revision=digest).consume()

    def search(self, question, limit=3):
        if not question.strip() or len(question) > 8000 or not 1 <= limit <= 10:
            raise ValueError("Use a non-empty question of at most 8000 characters and limit 1..10")
        return self.query(
            "CALL db.index.vector.queryNodes('document_embeddings', $limit, $vector) "
            "YIELD node AS d, score RETURN d.id AS document_id, d.title AS title, "
            "d.source AS source, d.text AS text, score",
            limit=limit, vector=self.vector(question),
        )

    def context(self, document_id):
        # Expand one graph hop from entities mentioned in the retrieved document.
        return self.query(
            "MATCH (:Document {id: $id})-[:MENTIONS]->(e:Entity) "
            "MATCH (e)-[r:RELATION]-(neighbor:Entity) "
            "RETURN DISTINCT startNode(r).name AS subject, r.kind AS relation, "
            "endNode(r).name AS object, r.document_id AS document_id, r.source AS source "
            "ORDER BY document_id, subject, relation, object LIMIT 50",
            id=document_id,
        )
