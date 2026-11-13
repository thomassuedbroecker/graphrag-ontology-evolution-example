# SPDX-License-Identifier: Apache-2.0
import copy
import unittest

from local_graphrag.data import fingerprint, load_documents, validate


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.doc = copy.deepcopy(load_documents("data/documents")[0])

    def test_unknown_ontology_and_invalid_relationship_rejected(self):
        for mutate in (
            lambda d: d.update(ontology_version="2"),
            lambda d: d["entities"][0].update(type="Unknown"),
            lambda d: d["facts"][0].update(relation="VISITS"),
            lambda d: d["facts"][0].update(object="missing"),
        ):
            with self.subTest(mutate=mutate):
                doc = copy.deepcopy(self.doc)
                mutate(doc)
                with self.assertRaises(ValueError):
                    validate(doc)

    def test_digest_stable_but_changes_with_content_or_embedding_configuration(self):
        digest = fingerprint(self.doc, "model", 768)
        reordered = dict(reversed(list(self.doc.items())))
        self.assertEqual(digest, fingerprint(reordered, "model", 768))
        self.assertNotEqual(digest, fingerprint(self.doc, "other-model", 768))
        self.assertNotEqual(digest, fingerprint(self.doc, "model", 384))
        self.doc["text"] += " Changed."
        self.assertNotEqual(digest, fingerprint(self.doc, "model", 768))

    def test_malformed_documents_raise_readable_errors(self):
        for mutate, message in (
            (lambda d: d.pop("entities"), r"missing required fields: \['entities'\]"),
            (lambda d: d["entities"][0].pop("type"), "Entity is missing required fields"),
            (lambda d: d["facts"][0].pop("subject"), "Fact is missing required fields"),
            (lambda d: d.update(title=" "), "Document requires"),
        ):
            with self.subTest(message=message):
                doc = copy.deepcopy(self.doc)
                mutate(doc)
                with self.assertRaisesRegex(ValueError, message):
                    validate(doc)

    def test_evidence_and_source_version_are_checked_when_present(self):
        fact = self.doc["facts"][0]
        quote = "Orbital Flights"
        valid = {**fact, "quote": quote}
        validate({**self.doc, "evidence": [valid]})
        for evidence, message in (
            ([{**valid, "object": "moon"}], "undeclared fact"),
            ([{**valid, "quote": "Not in the passage"}], "does not appear"),
            ([{**fact}], "Evidence is missing required fields"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate({**self.doc, "evidence": evidence})
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate({**self.doc, "source_version": "abc"})


if __name__ == "__main__":
    unittest.main()
