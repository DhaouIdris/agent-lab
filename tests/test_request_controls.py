from datetime import datetime
import unittest
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from experiments.request_controls import check_emergency_intent, redact_pii, resolve_temporal_context
from experiments.unified_agent import ask


class RequestControlsTests(unittest.TestCase):
    def test_urgent_request_stops_before_chat_or_route(self):
        client=Mock()
        result=ask(client,'missing.sqlite',[],'Je fais un malaise, au secours !')
        self.assertEqual(result['guard_status'],'emergency_short_circuit')
        self.assertIn('185',result['output']['answer'])
        client.chat.assert_not_called()
        english=ask(client,'missing.sqlite',[],"I can't breathe, help me")
        self.assertIn('call 185',english['output']['answer'])
        client.chat.assert_not_called()
        self.assertFalse(check_emergency_intent('Quelle est l’histoire du SAMU ?'))

    def test_common_pii_redacted_before_model_and_private_batch_log(self):
        from experiments.unified_agent_batch import run
        from pathlib import Path
        import json, tempfile
        message='Mon courriel est idris@example.com et mon téléphone +225 0102030405. Quel est le PIB ?'
        scrubbed=redact_pii(message)
        self.assertNotIn('idris@example.com',scrubbed)
        self.assertNotIn('0102030405',scrubbed)
        self.assertEqual(redact_pii('Carte 4111 1111 1111 1111'), 'Carte [CARTE_MASQUÉE]')
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'places.sqlite';db.touch()
            client=Mock();client.calls=[]
            client.chat.return_value={'content':json.dumps({'answer':'Je ne peux pas vérifier ce fait.',
                                                   'document_ids':[],'place_ids':[],'abstain':True})}
            case={'id':'PII-1','question':message,'human_expectation':'Ne pas exposer la donnée personnelle',
                  'required_tools':[]}
            result=run(client,db,[],[case])
            self.assertEqual(result['results'][0]['question'],scrubbed)
            self.assertEqual(client.chat.call_args.args[0][1]['content'],scrubbed)

    def test_relative_dates_are_local_and_holidays_unverified(self):
        ts=datetime(2026,11,27,23,30,tzinfo=ZoneInfo('Africa/Abidjan'))
        ctx=resolve_temporal_context('Demain et ce week-end',ts)
        self.assertEqual(ctx['resolved_dates']['tomorrow'],'2026-11-28')
        self.assertEqual(ctx['resolved_dates']['weekend'],['2026-11-28','2026-11-29'])
        self.assertEqual(ctx['holidays'],'unavailable_without_verified_calendar')


if __name__=='__main__':unittest.main()
