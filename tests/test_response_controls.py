import unittest

from experiments.response_controls import verify_and_render


class ResponseControlsTests(unittest.TestCase):
    def setUp(self):
        self.evidence={'RULE-1':{'title':'Guide officiel','updated_at':'2026-11-20'}}
        self.handoffs={'HND-1':'https://example.gouv.ci/demarche'}

    def test_renders_only_observed_citation_and_application_handoff(self):
        answer='La démarche est décrite ici [CIT:RULE-1]. [[HANDOFF:HND-1]]'
        rendered=verify_and_render(answer,['RULE-1'],self.evidence,self.handoffs,'Quel passeport ?',False)
        self.assertIn('Guide officiel, mise à jour 2026-11-20',rendered)
        self.assertIn('https://example.gouv.ci/demarche',rendered)

    def test_invalid_reference_or_free_url_is_rejected(self):
        for answer in ('Consultez https://untrusted.example',
                       'Voyez [CIT:INVENTED].',
                       'La démarche est simple [CIT:RULE-1]. [[HANDOFF:OTHER]]',
                       'Le passeport est toujours délivré en 24 h.'):
            with self.subTest(answer=answer),self.assertRaises(ValueError):
                verify_and_render(answer,['RULE-1'],self.evidence,self.handoffs,
                                  'Comment obtenir un passeport ?',False)
        # A justified abstention may be given without a regulatory source.
        self.assertEqual(verify_and_render('Information indisponible.',[],{},self.handoffs,
                         'Comment obtenir un passeport ?',True),'Information indisponible.')


if __name__=='__main__':unittest.main()
