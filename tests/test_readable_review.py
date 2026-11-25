import json
import tempfile
import unittest
from pathlib import Path

from experiments.readable_review import render, review_markdown


class ReadableReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.review = {
            'campaign_complete': True,
            'config': {'model': 'example', 'api_key': 'DO-NOT-COPY-THIS-KEY'},
            'results': [
                {'id': 'H-L08', 'repetition': 1, 'category': 'dialogue', 'status': 'model_output',
                 'automatic_checks_pass': False, 'quality_checks': {'required_document_ids': False},
                 'question': 'Décris la Comoé et <script>malicious</script>.',
                 'human_expectation': 'Parc national et citation.',
                 'review_guide': {'supported':['Le fleuve traverse le parc.'],
                                  'not_supported':['Des crues annuelles sont attestées.']},
                 'output': {'answer': '````\n# Titre trompeur\n````', 'abstain': False,
                            'document_ids': ['UNESCO_COMOE__0001'], 'place_ids': []},
                 'trace': [{'tool': 'search_documents', 'arguments': {'query': 'parc'},
                            'result': {'passages': [{'id': 'UNESCO_COMOE__0001', 'title': 'Comoé',
                                                     'publisher': 'UNESCO', 'text': 'La végétation du parc.'}]}}],
                 'rejected_responses_private': [{'validation_error': 'unsupported_price_or_time',
                                                 'rejected_model_content': 'Le parc ouvre à 9 h.'}]},
                {'id': 'H-L08', 'repetition': 2, 'category': 'dialogue', 'status': 'model_output',
                 'automatic_checks_pass': True, 'question': 'Décris la Comoé.',
                 'human_expectation': 'Citer le parc.',
                 'output': {'answer': 'Parc de la Comoé.', 'abstain': False, 'document_ids': [], 'place_ids': []},
                 'trace': [{'tool': 'search_catalogue', 'result': {'items': [{'source_id': 'node/1',
                                                            'name': 'Lieu', 'category': 'cafe', 'district': ''}]}}]},
            ],
        }

    def test_renders_answers_sources_rejections_and_review_checks(self):
        rendered = review_markdown(self.review)
        self.assertIn('Exécutions affichées : **2**', rendered)
        self.assertIn('H-L08 / 1', rendered)
        self.assertIn('H-L08 / 2', rendered)
        self.assertIn('required_document_ids', rendered)
        self.assertIn('La végétation du parc.', rendered)
        self.assertIn('Repères de fidélité', rendered)
        self.assertIn('Des crues annuelles sont attestées.', rendered)
        self.assertIn('pas nécessairement faux', rendered)
        self.assertIn('Passage retourné (cité)', rendered)
        self.assertIn('Le parc ouvre à 9 h.', rendered)
        self.assertIn('Lieu retourné (non mentionné)', rendered)
        self.assertEqual(rendered.count('- [ ] Faits étayés'), 2)
        self.assertNotIn('DO-NOT-COPY-THIS-KEY', rendered)
        self.assertIn('`````text\n````\n# Titre trompeur\n````\n`````', rendered)

    def test_other_passages_are_compact_unless_requested_and_duplicate_hits_fold(self):
        first = self.review['results'][0]
        other = {'id': 'UNESCO_TAI__0001', 'title': 'Taï', 'text': 'Autre long extrait.'}
        first['trace'][0]['result']['passages'].append(other)
        first['trace'].append(first['trace'][0].copy())
        compact = review_markdown(self.review)
        self.assertEqual(compact.count('La végétation du parc.'), 1)
        self.assertIn('Autre passage retourné (extrait masqué)', compact)
        self.assertNotIn('Autre long extrait.', compact)
        full = review_markdown(self.review, all_sources=True)
        self.assertIn('Autre long extrait.', full)

    def test_filters_and_writes_only_private_markdown(self):
        source = self.dir / 'review.private.json'
        source.write_text(json.dumps(self.review), encoding='utf-8')
        result = render(self.dir, case_ids=('H-L08',), failed_only=True)
        self.assertEqual(result, self.dir / 'review.readable.private.md')
        self.assertIn('H-L08 / 1', result.read_text(encoding='utf-8'))
        self.assertNotIn('H-L08 / 2', result.read_text(encoding='utf-8'))
        self.assertEqual(json.loads(source.read_text(encoding='utf-8')), self.review)
        with self.assertRaises(ValueError):
            render(source, output=source)
        with self.assertRaises(ValueError):
            review_markdown(self.review, case_ids=('missing',))

    def test_old_redacted_trace_must_not_claim_missing_sources(self):
        sample = self.review['results'][0].copy()
        sample['trace'] = [{'tool': 'search_documents', 'result_count': 2}]
        sample['output'] = None
        text = review_markdown({'results': [sample], 'campaign_complete': False})
        self.assertIn('Résultat expurgé ou indisponible', text)
        self.assertIn('Campagne incomplète', text)


if __name__ == '__main__':
    unittest.main()
