# SPDX-License-Identifier: Apache-2.0
"""Opt-in integration tests against a dedicated demo Neo4j database; rerunnable, ends on the baseline."""
import copy
import os
import unittest


@unittest.skipUnless(os.getenv("RUN_SERVICE_TESTS") == "1", "requires dedicated local Neo4j and Ollama")
class ServiceTests(unittest.TestCase):
    def test_import_noop_update_provenance_and_rollback(self):
        from local_graphrag.config import Settings
        from local_graphrag.data import load_documents
        from local_graphrag.store import Store
        store = Store(Settings.load())
        if store.active_ontology()["version"] != "1":
            store.close()
            self.skipTest("graph is migrated; reset with ./scripts/stop.sh --delete-data")
        docs = load_documents("data/documents")
        try:
            store.schema()
            store.apply(docs)
            self.assertTrue(all(p["action"] == "unchanged" for p in store.plan(docs)))
            changed = copy.deepcopy(docs)
            changed[0]["text"] += " Integration test revision."
            store.apply(changed)
            from local_graphrag.data import fingerprint
            digest = fingerprint(changed[0], store.settings.embed_model, store.settings.dimensions)
            self.assertEqual(store.query(
                "MATCH (d:Document {id:$id})-[:HAS_REVISION]->(v:Revision {id:$rev}) "
                "WHERE d.hash = $hash RETURN v.id", id=docs[0]["id"],
                rev=f"{docs[0]['id']}:{digest}", hash=digest), [{"v.id": f"{docs[0]['id']}:{digest}"}])
            self.assertTrue(store.search("Which destination can Galaxium customers visit?"))
            self.assertTrue(any(r["document_id"] == "lunar-itinerary" for r in store.context("company-overview")))
            broken = copy.deepcopy(changed)
            broken[0]["text"] += " Must roll back."
            broken[1]["entities"][0]["name"] = "Conflicting name"
            with self.assertRaises(ValueError):
                store.apply(broken)
            self.assertTrue(all(p["action"] == "unchanged" for p in store.plan(changed)))
            store.apply(docs)
            new_service = load_documents("data/scenarios/new-service/documents")
            store.apply(new_service)
            offers = store.query("MATCH (:Entity {id:'galaxium'})-[r:RELATION {kind:'OFFERS', document_id:'company-overview'}]->(e) RETURN e.id AS id")
            self.assertEqual({row["id"] for row in offers},
                             {"orbital-flights", "lunar-excursions", "space-hotel-stays", "lunar-photography-tours"})
            self.assertTrue(all(p["action"] == "unchanged" for p in store.plan(new_service)))
            store.apply(docs)
        finally:
            store.close()
