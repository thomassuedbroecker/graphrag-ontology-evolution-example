# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_graphrag.data import (
    ENTITY_TYPES, ONTOLOGY_VERSION, RELATIONS, V1, check_migration, load_documents, load_ontology,
    migrate_document, ontology_diff, validate,
)
from local_graphrag.prepare import prepare_documents


class ArchitectureDataTests(unittest.TestCase):
    def test_scenario_manifest_paths_and_selected_schemas_are_consistent(self):
        manifest = json.loads(Path('data/scenarios/manifest.json').read_text())
        baseline = load_documents('data/documents')
        baseline_facts = {tuple(f[k] for k in ('subject', 'relation', 'object'))
                          for d in baseline for f in d['facts']}
        for scenario in manifest['scenarios']:
            with self.subTest(scenario=scenario['id']):
                self.assertTrue(Path(scenario['source']).is_file())
                if 'documents' in scenario:
                    ontology = load_ontology(scenario['ontology'])
                    docs = load_documents(scenario['documents'], ontology)
                    self.assertTrue(docs)
                    if 'expected_facts' in scenario:
                        self.assertEqual(sum(len(d['facts']) for d in docs), scenario['expected_facts'])
                    if scenario['expected_route'] == 'data-update':
                        self.assertEqual(docs, load_documents(scenario['documents']))
                    else:
                        with self.assertRaisesRegex(ValueError, 'Unsupported ontology version'):
                            load_documents(scenario['documents'])
                else:
                    docs = prepare_documents(scenario['source'])
                facts = {tuple(f[k] for k in ('subject', 'relation', 'object'))
                         for d in docs for f in d['facts']}
                if 'expected_added_facts' in scenario:
                    self.assertEqual(facts - baseline_facts,
                                     {tuple(f) for f in scenario['expected_added_facts']})

    def test_importer_uses_the_v1_json_specification(self):
        ontology = load_ontology('data/ontologies/v1.json')
        self.assertEqual(ontology['status'], 'baseline')
        self.assertEqual(ontology['version'], ONTOLOGY_VERSION)
        self.assertEqual(set(ontology['entity_types']), ENTITY_TYPES)
        self.assertEqual({k: tuple(v) for k, v in ontology['relations'].items()}, RELATIONS)

    def test_new_service_is_a_new_instance_under_v1_and_preserves_lunar_facts(self):
        before = load_documents('data/documents')
        after = load_documents('data/scenarios/new-service/documents')
        self.assertEqual(after, prepare_documents('data/scenarios/new-service/company-overview.md'))
        self.assertEqual(before[1], after[1])
        self.assertEqual([f for f in after[0]['facts'] if f not in before[0]['facts']],
                         [{'subject':'galaxium', 'relation':'OFFERS', 'object':'lunar-photography-tours'}])
        self.assertTrue(all(f in after[0]['facts'] for f in before[0]['facts']))

    def test_training_fact_has_source_evidence_but_needs_a_model_change(self):
        ontology = load_ontology('data/ontologies/v2.json')
        candidate = load_documents('data/scenarios/training-requirement/candidates', ontology)[0]
        source = Path('data/scenarios/training-requirement/lunar-training-policy.md').read_text()
        self.assertEqual(candidate['source_version'], hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(candidate['evidence'][0]['quote'], candidate['text'])
        self.assertIn(candidate['text'], source)
        self.assertEqual({k: candidate['evidence'][0][k] for k in ('subject','relation','object')},
                         candidate['facts'][0])
        self.assertEqual(set(ontology['entity_types']) - ENTITY_TYPES, {'Training'})
        self.assertEqual(set(ontology['relations']) - set(RELATIONS), {'REQUIRES'})
        disguised = copy.deepcopy(candidate)
        disguised['ontology_version'] = '1'
        with self.assertRaisesRegex(ValueError, 'Unknown entity type: Training'):
            validate(disguised)
        # Both parts of the model change matter: adding a type alone is insufficient.
        only_type = {**ontology, 'relations': {k:list(v) for k,v in RELATIONS.items()}}
        with self.assertRaisesRegex(ValueError, 'Invalid ontology relation'):
            validate(candidate, only_type)

    def test_validate_cli_rejects_training_under_v1_and_accepts_v2(self):
        cli = [sys.executable, '-m', 'local_graphrag', 'validate',
               '--data', 'data/scenarios/training-requirement/candidates']
        rejected = subprocess.run(cli, capture_output=True, text=True, timeout=30)
        self.assertEqual(rejected.returncode, 1)
        self.assertNotIn('Traceback', rejected.stderr)
        self.assertIn('Rejected under built-in v1', rejected.stderr)
        self.assertIn('training.json', rejected.stderr)
        accepted = subprocess.run(cli + ['--ontology', 'data/ontologies/v2.json'],
                                  capture_output=True, text=True, timeout=30, check=True)
        self.assertIn("follows the graph's active ontology", accepted.stdout)

    def test_v1_passage_fits_because_it_omits_the_dependency(self):
        passage = load_documents('data/scenarios/training-requirement/v1-passage')[0]
        candidate = load_documents('data/scenarios/training-requirement/candidates',
                                   load_ontology('data/ontologies/v2.json'))[0]
        self.assertEqual(passage['facts'], [])
        self.assertEqual({k: passage[k] for k in ('id', 'text', 'source', 'source_version')},
                         {k: candidate[k] for k in ('id', 'text', 'source', 'source_version')})
        self.assertNotIn('Training', {e['type'] for e in passage['entities']})

    def test_unstructured_json_is_rejected_not_ignored(self):
        with self.assertRaisesRegex(ValueError, r"fields outside the document format: \['policy'\]"):
            load_documents('data/scenarios/training-requirement/unstructured')
        passage = load_documents('data/scenarios/training-requirement/v1-passage')[0]
        cases = [
            ({**passage, 'payload': {'any': 'json'}}, 'fields outside the document format'),
            ({**passage, 'entities': [{**passage['entities'][0], 'requires': 'x'}]}, "Entity has fields outside"),
            ({**passage, 'facts': [{'subject': 'a', 'relation': 'OFFERS', 'object': 'b', 'since': '2026'}]},
             'Fact has fields outside'),
            ({k: v for k, v in passage.items() if k != 'facts'}, r"missing required fields: \['facts'\]"),
            ({**passage, 'text': '{"service": "Lunar Excursions"}'}, 'not embedded JSON'),
            ({**passage, 'id': 'Lunar Training'}, 'lowercase slug'),
        ]
        for document, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate(document)

    def test_v2_is_an_additive_approved_successor_of_v1(self):
        v2 = load_ontology('data/ontologies/v2.json')
        diff = check_migration(V1, v2)
        self.assertEqual(diff['added_types'], ['Training'])
        self.assertEqual(diff['added_relations'], {'REQUIRES': ['Service', 'Training']})
        self.assertEqual(diff['unchanged_relations'], ['OFFERS', 'VISITS'])
        self.assertTrue(diff['compatible'])
        with self.assertRaisesRegex(ValueError, 'already on ontology 2'):
            check_migration(v2, v2)
        with self.assertRaisesRegex(ValueError, 'not approved'):
            check_migration(V1, {**v2, 'status': 'proposed'})
        narrowed = {**v2, 'relations': {**v2['relations'], 'VISITS': ['Company', 'Destination']}}
        self.assertEqual(ontology_diff(V1, narrowed)['changed_relations'],
                         {'VISITS': {'from': ['Service', 'Destination'], 'to': ['Company', 'Destination']}})
        with self.assertRaisesRegex(ValueError, 'Only additive'):
            check_migration(V1, narrowed)

    def test_every_lab_document_migrates_to_v2_unchanged_except_the_label(self):
        v2 = load_ontology('data/ontologies/v2.json')
        for folder in ('data/documents', 'data/scenarios/new-service/documents',
                       'data/scenarios/training-requirement/v1-passage'):
            for doc in load_documents(folder):
                self.assertEqual(migrate_document(doc, v2), {**doc, 'ontology_version': '2'})
        self.assertEqual(prepare_documents('data/input-documents/galaxium-travels-company_overview.md', v2),
                         [migrate_document(d, v2) for d in load_documents('data/documents')])

    def test_invalid_ontology_endpoints_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ontology.json'
            path.write_text(json.dumps({'version':'2','status':'proposed','entity_types':['Service'],
                                       'relations':{'REQUIRES':['Service','Missing']}}))
            with self.assertRaisesRegex(ValueError, 'endpoints'):
                load_ontology(path)
