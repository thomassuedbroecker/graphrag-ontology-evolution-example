# SPDX-License-Identifier: Apache-2.0
import tempfile
import unittest
from pathlib import Path

from local_graphrag.data import load_documents
from local_graphrag.prepare import prepare_documents, write_documents


BASELINE = Path("data/input-documents/galaxium-travels-company_overview.md")


class PreparationTests(unittest.TestCase):
    def test_checked_in_documents_match_the_input_source(self):
        documents = prepare_documents(BASELINE)
        self.assertEqual(documents, load_documents("data/documents"))
        self.assertNotIn("mars", {e["id"] for d in documents for e in d["entities"]})

    def test_each_document_cites_its_own_source_anchor(self):
        company, lunar = prepare_documents(BASELINE)
        self.assertEqual(company["source"], "galaxium:company-overview#primary-services")
        self.assertEqual(lunar["source"], "galaxium:company-overview#lunar-excursions")

    def test_changed_details_are_captured_and_unknown_services_require_review(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.md"
            source.write_text(BASELINE.read_text().replace("7-day lunar orbit", "10-day lunar orbit"))
            docs = write_documents(source, Path(temp) / "documents")
            self.assertEqual(docs, load_documents(Path(temp) / "documents"))
            self.assertIn("10-day lunar orbit", docs[1]["text"])
            original = prepare_documents(BASELINE)
            self.assertNotEqual(original[1]["source_version"], docs[1]["source_version"])
            source.write_text(BASELINE.read_text().replace("Orbital Flights 1.", "Mystery Flights 1."))
            with self.assertRaisesRegex(ValueError, "review the mapping"):
                prepare_documents(source)
