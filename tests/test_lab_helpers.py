# SPDX-License-Identifier: Apache-2.0
"""Offline tests for the Lab 9-12 helper scripts; no Neo4j or Ollama needed."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_discover import candidate_slots, curated_document, gate  # noqa: E402
from lab_graph import check_fact, repair_hint  # noqa: E402
from lab_impact import migration_verdict  # noqa: E402
from lab_regression import compare, expected_from_sources  # noqa: E402

from local_graphrag.data import load_ontology, validate  # noqa: E402
from local_graphrag.prepare import prepare_documents  # noqa: E402

V1 = load_ontology(ROOT / "data/ontologies/v1.json")
V2 = load_ontology(ROOT / "data/ontologies/v2.json")
V3 = load_ontology(ROOT / "data/scenarios/breaking-change/v3-breaking.json")


def graph_after_lab_10():
    """Current snapshots after Lab 7: new-service documents plus the training fact, all on v2."""
    documents = prepare_documents(ROOT / "data/scenarios/new-service/company-overview.md", V2)
    training = json.loads((ROOT / "data/scenarios/training-requirement/candidates/training.json").read_text())
    documents.append(validate(training, V2))
    return {d["id"]: {"revision": "test", "document": d} for d in documents}


class FactCheckTests(unittest.TestCase):
    def test_v3_invalidates_visits_and_requires_with_repair_hints(self):
        lunar = graph_after_lab_10()["lunar-itinerary"]["document"]
        entities = {e["id"]: e for e in lunar["entities"]}
        visits = lunar["facts"][0]
        self.assertIsNone(check_fact(visits, entities, V2))
        self.assertEqual(check_fact(visits, entities, V3), "relation VISITS removed")
        self.assertTrue(repair_hint(visits, entities, V2, V3).startswith("mechanical: rename to TRAVELS_TO"))

        policy = graph_after_lab_10()["lunar-training-policy"]["document"]
        entities = {e["id"]: e for e in policy["entities"]}
        requires = policy["facts"][0]
        self.assertIn("now connects Destination -> Training", check_fact(requires, entities, V3))
        self.assertTrue(repair_hint(requires, entities, V2, V3).startswith("re-extract"))


class ImpactTests(unittest.TestCase):
    def test_migration_verdict_matches_importer_checks(self):
        self.assertTrue(migration_verdict(V1, V2).startswith("accepted"))
        self.assertIn("already on ontology 2", migration_verdict(V2, V2))
        self.assertIn("Only additive migrations", migration_verdict(V2, V3))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.documents = graph_after_lab_10()
        self.entities, self.slots = candidate_slots(self.documents, V2)

    def test_six_candidate_slots_as_in_lab_11(self):
        self.assertEqual(sorted(f"{s} {r} {o}" for s, r, o in self.slots), sorted([
            "lunar-photography-tours REQUIRES lunar-surface-safety",
            "orbital-flights REQUIRES lunar-surface-safety",
            "space-hotel-stays REQUIRES lunar-surface-safety",
            "lunar-photography-tours VISITS moon",
            "orbital-flights VISITS moon",
            "space-hotel-stays VISITS moon",
        ]))

    def test_gate_rejects_malformed_invented_and_unquoted_answers(self):
        slots = set(self.slots)
        good = {"subject": "lunar-photography-tours", "relation": "VISITS", "object": "moon",
                "supported": True, "document": "company-overview",
                "quote": "Guided lunar photography experience"}
        cases = [
            ({}, "rejected: not a candidate slot"),
            ({**good, "object": "mars"}, "rejected: not a candidate slot"),
            ({**good, "supported": "yes"}, "not supported"),
            ({**good, "document": "missing"}, "rejected: unknown evidence document"),
            ({**good, "quote": "Moon landing included"}, "rejected: quote does not appear"),
            (good, "proposed: needs human review"),
        ]
        for answer, expected in cases:
            with self.subTest(expected=expected, answer=answer):
                self.assertTrue(gate(answer, slots, self.documents).startswith(expected))

    def test_generated_proposal_is_valid_and_labelled_unreviewed(self):
        answer = {"subject": "lunar-photography-tours", "relation": "VISITS", "object": "moon",
                  "document": "company-overview", "quote": "Guided lunar photography experience"}
        document = curated_document(answer, self.entities, self.documents, V2)
        self.assertIn("not reviewed", document["text"])
        self.assertNotIn("reviewed by a person", document["text"])
        self.assertEqual(document["facts"], [{"subject": "lunar-photography-tours",
                                              "relation": "VISITS", "object": "moon"}])


class RegressionTests(unittest.TestCase):
    def test_offline_rebuild_matches_ground_truth(self):
        truth = json.loads((ROOT / "data/scenarios/regression/ground-truth.json").read_text())
        actual = expected_from_sources(truth)
        for name, expected in (("documents", truth["documents"]), ("facts", truth["facts"]),
                               ("entity_types", truth["entity_types"])):
            with self.subTest(check=name):
                self.assertTrue(compare(name, expected, actual[name])["passed"])

    def test_compare_reports_missing_and_unexpected(self):
        result = compare("facts", ["a", "b"], ["b", "c"])
        self.assertEqual((result["passed"], result["missing"], result["unexpected"]), (False, ["a"], ["c"]))


if __name__ == "__main__":
    unittest.main()
