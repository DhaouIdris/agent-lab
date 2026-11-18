import hashlib
import json
import unittest
from pathlib import Path
from experiments.document_rag import load_corpus
from experiments.ingest_text_documents import build_corpus


class UNESCODataTests(unittest.TestCase):
    def test_offsets_hash_and_provenance(self):
        root=Path('data/unesco_source_texts')
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'))
        by_id={d['id']:d for d in manifest}
        docs=load_corpus('data/rag_unesco_descriptions.json')
        self.assertEqual(len(by_id),5)
        for doc in docs:
            entry=by_id[doc['source_doc_id']]
            raw=(root/entry['file']).read_bytes();text=raw.decode('utf8')
            self.assertEqual(doc['source_file_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(doc['text'],text[doc['start_char']:doc['end_char']])
            self.assertEqual(doc['content_type'],'licensed_excerpt')
            self.assertNotIn('rights_confirmed_by_user',doc)
            self.assertIn('creativecommons.org',doc['license_note'])

    def test_pilot_cases_use_known_sources(self):
        docs=load_corpus('data/rag_unesco_descriptions.json')
        cases=json.loads(Path('data/rag_unesco_descriptions_dev_cases.json').read_text(encoding='utf8'))
        self.assertEqual(len(cases),12)
        self.assertTrue(all(set(c['relevant_ids'])<={d['id'] for d in docs} for c in cases))

    def test_generation_requests_uncertainty_and_relevant_citations(self):
        from unittest.mock import Mock
        from experiments.document_rag import generate, retrieve
        docs=load_corpus('data/rag_unesco_descriptions.json')
        hits=retrieve('De quelle ville provient le style architectural des mosquées ?',docs)
        client=Mock()
        client.chat.return_value={'content':json.dumps({'answer':'La source indique que l’origine se situerait à Djenné.','citation_ids':['UNESCO_MOSQUEES__0002'],'abstain':False})}
        result=generate(client,'De quelle ville provient le style architectural des mosquées ?',hits)
        system=client.chat.call_args.args[0][0]['content']
        self.assertIn('never turn a possibility, hypothesis, estimate or uncertainty into a categorical assertion',system)
        self.assertIn('Cite only passages that directly support at least one substantive claim',system)
        self.assertEqual(result['citation_ids'],['UNESCO_MOSQUEES__0002'])
