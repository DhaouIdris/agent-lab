import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from pydantic import ValidationError

from experiments.territory_tools import MODELS, TerritoryTools, tool_spec
from experiments.unified_agent import ask


class TerritoryToolsTests(unittest.TestCase):
    def test_all_schemas_are_strict_closed_and_require_every_field(self):
        self.assertEqual(len(MODELS),6)
        for name in MODELS:
            with self.subTest(name=name):
                spec=tool_spec(name)['function']
                schema=spec['parameters']
                self.assertTrue(spec['strict'])
                self.assertIs(schema['additionalProperties'],False)
                self.assertEqual(set(schema['properties']),set(schema['required']))

    def test_missing_adapter_cannot_claim_an_empty_official_feed(self):
        result=TerritoryTools().execute('get_official_alerts',{
            'domains':['public_safety'],'area_label':None,'min_severity':'advisory'})
        self.assertEqual(result['status'],'SERVICE_UNAVAILABLE')
        self.assertEqual(TerritoryTools().specs(),[])

    def test_entity_details_require_prior_matching_registry_and_source(self):
        def directory(args,timeout):
            return {'status':'ok','source':{'publisher':'Test directory','updated_at':'2026-11-24'},
                    'items':[{'entity_id':'svc-1','name':'Example'}]}
        def details(args,timeout):
            return {'status':'ok','source':{'publisher':'Test directory','updated_at':'2026-11-24'},
                    'items':[{'entity_id':args.entity_id,'name':'Example'}]}
        tools=TerritoryTools({'search_public_services':directory,'get_entity_details':details})
        args={'entity_id':'svc-1','source_registry':'public_services','target_datetime_iso':None}
        self.assertEqual(tools.execute('get_entity_details',args)['status'],'UNKNOWN_ENTITY')
        tools.execute('search_public_services',{'category':'administration','query':None,
            'origin_label':None,'target_datetime_iso':None,'pmr_accessible':None,
            'language_spoken':None,'limit':5})
        self.assertEqual(tools.execute('get_entity_details',args)['status'],'ok')
        self.assertEqual(tools.execute('get_entity_details',{**args,'source_registry':'catalogue_chr'})['status'],'UNKNOWN_ENTITY')

    def test_unsafe_or_unverified_requests_fail_validation(self):
        tools=TerritoryTools()
        cases=[('search_events_agenda',{'start_date_iso':'2026-02-30','end_date_iso':'2026-03-01',
                'event_type':None,'query':None,'free_entry_only':None,'limit':5}),
               ('get_transit_options',{'origin_label':'A','destination_label':'B',
                'departure_datetime_iso':'2026-11-24T10:00:00',
                'wheelchair_accessible':False,'modes':['bus']}),
               ('get_transit_options',{'origin_label':'A','destination_label':'B',
                'departure_datetime_iso':None,'wheelchair_accessible':False,'modes':['metro']}),
               ('get_official_alerts',{'domains':['weather','weather'],
                'area_label':None,'min_severity':'info'}),
               ('lookup_procedure_rules',{'procedure_topic':'unlisted','user_profile':'unknown',
                'specific_question':None}),
               ('lookup_procedure_rules',{'procedure_topic':'parking_low_emission_zone',
                'user_profile':'eu_visitor','specific_question':None})]
        for name,args in cases:
            with self.subTest(name=name),self.assertRaises(ValidationError):
                tools.execute(name,args)
        with self.assertRaises(ValidationError):
            tools.execute('get_official_alerts',{'domains':['weather'],'area_label':None,
                'min_severity':'info','extra':'untrusted'})

    def test_adapter_success_without_provenance_is_rejected(self):
        tools=TerritoryTools({'get_official_alerts':lambda args,timeout:{'status':'ok','items':[]}})
        with self.assertRaises(ValueError):
            tools.execute('get_official_alerts',{'domains':['weather'],'area_label':None,
                'min_severity':'info'})

    def test_configured_tool_exposes_evidence_and_rejects_injected_text(self):
        def adapter(args,timeout):
            return {'status':'ok','source':{'publisher':'Test publisher','updated_at':'2026-11-24'},
                    'items':[],'passages':[{'id':'TEST-1','text':'Le guichet accueille sur rendez-vous.'}]}
        tools=TerritoryTools({'lookup_procedure_rules':adapter})
        client=Mock()
        client.chat.side_effect=[{'content':None,'tool_calls':[{'id':'call1','type':'function',
            'function':{'name':'lookup_procedure_rules','arguments':json.dumps({
                'procedure_topic':'identity_passport','user_profile':'unknown','specific_question':None})}}]},
            {'content':json.dumps({'answer':'Le guichet accueille sur rendez-vous [CIT:TEST-1].',
                                    'document_ids':['TEST-1'],'place_ids':[],'abstain':False})}]
        with TemporaryDirectory() as temp:
            db=Path(temp)/'places.sqlite';db.touch()
            result=ask(client,db,[],'Comment renouveler mon passeport ?',territory_tools=tools)
        self.assertEqual(result['output']['document_ids'],['TEST-1'])
        self.assertIn('lookup_procedure_rules',
                      [x['function']['name'] for x in client.chat.call_args_list[0].kwargs['tools_override']])
        bad=TerritoryTools({'search_public_services':lambda args,timeout:{
            'status':'ok','source':{'publisher':'Test','updated_at':'2026-11-24'},
            'items':[{'entity_id':'x','name':'https://unverified.example'}]}})
        with self.assertRaises(ValueError):
            bad.execute('search_public_services',{'category':'administration','query':None,
                 'origin_label':None,'target_datetime_iso':None,'pmr_accessible':None,
                 'language_spoken':None,'limit':5})
        bad_source=TerritoryTools({'get_official_alerts':lambda args,timeout:{
            'status':'ok','source':{'publisher':'Test','updated_at':'2026-11-24',
                                     'url':'https://untrusted.example'},'items':[]}})
        with self.assertRaises(ValueError):
            bad_source.execute('get_official_alerts',{'domains':['weather'],
                'area_label':None,'min_severity':'info'})

    def test_handoff_requires_allowlist_and_observation_in_this_turn(self):
        def adapter(args,timeout):
            return {'status':'ok','source':{'publisher':'Test CI','updated_at':'2026-11-24'},
                    'items':[{'handoff_id':'HND-1'}],
                    'passages':[{'id':'RULE-1','text':'La démarche requiert un rendez-vous.'}]}
        tools=TerritoryTools({'lookup_procedure_rules':adapter},
                    handoffs={'HND-1':'https://example.gouv.ci/demarche'})
        reply={'content':None,'tool_calls':[{'id':'c1','type':'function',
            'function':{'name':'lookup_procedure_rules','arguments':json.dumps({
                'procedure_topic':'identity_passport','user_profile':'unknown',
                'specific_question':None})}}]}
        answer={'answer':'Un rendez-vous est requis [CIT:RULE-1]. [[HANDOFF:HND-1]]',
                'document_ids':['RULE-1'],'place_ids':[],'abstain':False}
        client=Mock();client.chat.side_effect=[reply,{'content':json.dumps(answer)}]
        with TemporaryDirectory() as temp:
            db=Path(temp)/'places.sqlite';db.touch()
            result=ask(client,db,[],'Comment obtenir un passeport ?',territory_tools=tools)
        self.assertIn('https://example.gouv.ci/demarche',result['output']['answer'])
        client=Mock();client.chat.return_value={'content':json.dumps(answer)}
        with TemporaryDirectory() as temp:
            db=Path(temp)/'places.sqlite';db.touch()
            rejected=ask(client,db,[],'Comment obtenir un passeport ?',territory_tools=tools)
        self.assertEqual(rejected['diagnostic_code'],'unobserved_document_ids')


if __name__=='__main__':unittest.main()
