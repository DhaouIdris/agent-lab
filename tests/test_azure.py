import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import run_azure
from ci_agentlab.evaluation import run_case
from ci_agentlab.preflight import check_endpoint
from ci_agentlab.providers import ChatClient, ProviderError, ToolAgent, safe_error_metadata

ROOT=Path(__file__).resolve().parents[1]

def config():
    c=json.loads((ROOT/'azure.example.json').read_text(encoding="utf-8"))
    c['base_url']='https://example.openai.azure.com/openai/v1'
    return c

def client(messages):
    c=ChatClient(config()['base_url'],'deployment',api_key='TEST_SECRET',
        auth_header='api-key',token_parameter='max_completion_tokens',max_calls=2)
    responses=[io.BytesIO(json.dumps({'choices':[{'message':m}],
        'usage':{'prompt_tokens':10,'completion_tokens':5}}).encode()) for m in messages]
    c.opener=Mock();c.opener.open.side_effect=responses
    return c

def tool_call():
    return {'content':None,'tool_calls':[{'id':'call_1','type':'function','function':{
        'name':'get_entity_details','arguments':'{"entity_id":"P1"}'}}]}

class AzureConfiguration(unittest.TestCase):
    def test_safe_error_metadata_drops_server_text_and_unknown_parameter(self):
        payload=json.dumps({'error':{'message':'secret URL and key','code':'invalid_request_error',
                                     'param':'response_format'}}).encode()
        error=urllib.error.HTTPError('https://example.org',400,'Bad Request',{},io.BytesIO(payload))
        self.assertEqual(safe_error_metadata(error),{'provider_error_code':'invalid_request_error',
                                                     'provider_error_param':'response_format'})
        payload=json.dumps({'error':{'code':'custom-secret','param':'my_secret'}}).encode()
        error=urllib.error.HTTPError('https://example.org',400,'Bad Request',{},io.BytesIO(payload))
        self.assertEqual(safe_error_metadata(error),{})
    def test_report_and_metadata_omit_endpoint_and_local_path(self):
        import argparse
        from ci_agentlab.__main__ import report_config
        endpoint='https://private-resource.openai.azure.com/openai/v1'
        cfg=report_config(argparse.Namespace(base_url=endpoint,out='C:/private/user/runs',api_key_env='SECRET_VAR',model='model'))
        self.assertEqual(cfg,{'model':'model'})
        meta=run_azure.public_config({**config(),'base_url':endpoint})
        self.assertNotIn(endpoint,json.dumps(meta))
        self.assertNotIn('base_url',meta)

    def load(self,c):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'azure.json';p.write_text(json.dumps(c),encoding='utf-8-sig')
            return run_azure.load_config(p)

    def test_valid_config_and_windows_bom(self):
        self.assertEqual(self.load(config()),config())

    def test_unsafe_or_wrong_endpoints_rejected(self):
        for url in ['http://example.com/openai/v1','https://user:secret@example.com/openai/v1',
                    'https://example.com/api/projects/p','https://example.com/openai/v1/chat/completions',
                    'https://example.com/openai/v1?api-key=secret']:
            with self.subTest(url=url),self.assertRaises(ValueError):self.load({**config(),'base_url':url})

    def test_secret_field_rejected_without_echo(self):
        with self.assertRaises(ValueError) as e:self.load({**config(),'api_key':'TEST_SECRET'})
        self.assertNotIn('TEST_SECRET',str(e.exception))

    def test_incomplete_and_non_object_config_rejected(self):
        for c in [{},[],{'base_url':'https://example.com/openai/v1'}]:
            with self.subTest(c=c),self.assertRaises(ValueError):self.load(c)

    def test_provisioned_and_invalid_parameters_rejected(self):
        for k,v in [('deployment_type','ProvisionedManaged'),('auth_header','password'),
                    ('token_parameter','limit'),('max_output_tokens',True),('turn_timeout_seconds',0),
                    ('min_interval_seconds',float('nan'))]:
            with self.subTest(k=k),self.assertRaises(ValueError):self.load({**config(),k:v})

    def test_prices_must_be_paired_finite_nonnegative(self):
        for a,b in [(1,None),(float('nan'),1),(1,float('inf')),(-1,1),(True,1)]:
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):
                self.load({**config(),'input_price_per_million':a,'output_price_per_million':b})

    def test_progressive_call_budgets(self):
        for stage,cap in [('smoke','24'),('pilot','400'),('benchmark','1200')]:
            cmd=run_azure.build_command(config(),stage,'out')
            self.assertEqual(cmd[cmd.index('--max-provider-calls')+1],cap)
            self.assertIn('--stop-on-provider-error',cmd)
            self.assertNotIn('TEST_SECRET',' '.join(cmd))
        self.assertEqual(run_azure.build_command(config(),'smoke','out').count('--case'),2)

    def test_dry_run_needs_no_key_or_network(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';p.write_text(json.dumps(config()),encoding='utf-8')
            r=subprocess.run([sys.executable,str(ROOT/'run_azure.py'),'smoke','--dry-run','--config',str(p)],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['network_calls'],0)

    def test_targeted_pilot_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';p.write_text(json.dumps(config()),encoding='utf-8')
            r=subprocess.run([sys.executable,str(ROOT/'run_azure.py'),'pilot','--case','I01','--dry-run','--config',str(p)],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)
            command=json.loads(r.stdout)['command']
            self.assertEqual(command[command.index('--case')+1],'I01')
            self.assertEqual(command[command.index('--base-url')+1],'[REDACTED]')
            self.assertEqual(command[command.index('--out')+1],'[REDACTED]')
            self.assertNotIn(config()['base_url'],r.stdout)

class AzureProtocol(unittest.TestCase):
    def test_stream_assembles_content_and_tool_arguments_before_return(self):
        def event(data):return b'data: '+json.dumps(data).encode()+b'\n\n'
        chunks=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'call_1','function':{'name':'echo_','arguments':'{"id":'}}]},'finish_reason':None}]},
                {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'name':'probe','arguments':'"P1"}'}}]},'finish_reason':'tool_calls'}]}]
        c=client([]);c.stream=True
        ticks=[];c.on_stream_chunk=lambda delta:ticks.append(delta)
        c.opener.open.side_effect=[io.BytesIO(b''.join(map(event,chunks))+b'data: [DONE]\n\n')]
        result=c.chat([{'role':'user','content':'test'}],tools_override=[])
        self.assertEqual(result['tool_calls'][0]['function'],{'name':'echo_probe','arguments':'{"id":"P1"}'})
        self.assertEqual(ticks,[])  # Tool-call argument fragments are never displayed.
        self.assertTrue(json.loads(c.opener.open.call_args.args[0].data)['stream'])

    def test_stream_delivers_content_fragments_as_they_arrive(self):
        def event(part,finish=None):
            return b'data: '+json.dumps({'choices':[{'delta':{'content':part},'finish_reason':finish}]}).encode()+b'\n\n'
        c=client([]);c.stream=True;seen=[]
        c.on_stream_chunk=seen.append
        c.opener.open.side_effect=[io.BytesIO(event('{"answer":"Bon')+event('jour"}', 'stop')+b'data: [DONE]\n\n')]
        self.assertEqual(c.chat([{'role':'user','content':'salut'}],tools_override=[])['content'],'{"answer":"Bonjour"}')
        self.assertEqual(seen,['{"answer":"Bon','jour"}'])

    def test_content_filter_is_distinct_from_agent_refusal(self):
        from ci_agentlab.evaluation import aggregate
        cases=json.loads((ROOT/'data/scenarios.json').read_text(encoding='utf-8'))
        case=next(x for x in cases if x['id']=='I01')
        c=client([])
        c.opener.open.side_effect=urllib.error.HTTPError(c.url,400,'filtered',{},io.BytesIO(b'{"error":{"code":"content_filter"}}'))
        r=run_case(case,client=c,stop_on_provider_error=True)
        self.assertEqual(r['evaluation_status'],'provider_filtered')
        self.assertFalse(r['auto_pass'])
        self.assertEqual(r['outputs'][0]['decision'],'abstain')
        summary=aggregate([r])
        self.assertEqual(summary['provider_filtered_runs'],1)
        self.assertIsNone(summary['automatic_pass_rate_evaluable_runs'])

    def test_unknown_400_is_not_classified_as_filter(self):
        from ci_agentlab.evaluation import is_provider_filtered
        self.assertFalse(is_provider_filtered({'error':'http','http_status':400}))
        self.assertFalse(is_provider_filtered({'error':'http','http_status':429,'provider_error_code':'content_filter'}))

    def test_retry_429_then_success_records_attempts(self):
        c=client([{'content':'{}'}]);c.max_calls=3
        good=c.opener.open.side_effect[0] if isinstance(c.opener.open.side_effect,list) else None
        good=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{}'}}], 'usage':{'prompt_tokens':1,'completion_tokens':1}}).encode())
        c.opener.open.side_effect=[urllib.error.HTTPError(c.url,429,'limit',{'Retry-After':'3'},None),good]
        with patch('ci_agentlab.providers.time.sleep') as sleep,patch('ci_agentlab.providers.random.uniform',return_value=1):
            self.assertEqual(c.chat([],timeout=30)['content'],'{}')
        sleep.assert_called_once_with(3)
        self.assertEqual(c.attempts,2)
        self.assertTrue(c.calls[0]['recovered_or_retried'])
        self.assertEqual(c.calls[0]['http_status'],429)

    def test_malformed_success_body_retries_with_bounded_jitter_and_safe_reason(self):
        c=client([]);c.max_calls=3
        good=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{}'}}], 'usage':{}}).encode())
        c.opener.open.side_effect=[io.BytesIO(b'{broken'), good]
        with patch('ci_agentlab.providers.time.sleep') as sleep, patch('ci_agentlab.providers.random.uniform',return_value=.5):
            self.assertEqual(c.chat([],timeout=30)['content'],'{}')
        sleep.assert_called_once_with(.5)
        self.assertEqual(c.attempts,2)
        self.assertEqual(c.calls[0]['error_kind'],'response_json')
        self.assertTrue(c.calls[0]['recovered_or_retried'])
        self.assertNotIn('broken',json.dumps(c.calls))

    def test_repeated_invalid_response_stops_after_three_calls_and_labels_schema(self):
        c=client([]);c.max_calls=3
        c.opener.open.side_effect=[io.BytesIO(b'{"choices":[]}') for _ in range(3)]
        with patch('ci_agentlab.providers.time.sleep'), patch('ci_agentlab.providers.random.uniform',return_value=.1):
            with self.assertRaises(ProviderError):c.chat([],timeout=30)
        self.assertEqual(c.attempts,3)
        self.assertEqual([x['error_kind'] for x in c.calls],['response_schema']*3)
        self.assertFalse(c.calls[-1].get('recovered_or_retried',False))

    def test_safe_diagnostic_does_not_log_body_or_secret(self):
        c=client([])
        body=io.BytesIO(b'{"error":{"code":"content_filter","message":"TEST_SECRET"}}')
        c.opener.open.side_effect=urllib.error.HTTPError(c.url,400,'bad',{},body)
        with self.assertRaises(ProviderError):c.chat([])
        self.assertEqual(c.calls[0]['provider_error_code'],'content_filter')
        self.assertNotIn('TEST_SECRET',json.dumps(c.calls))

    def test_two_call_preflight_and_azure_request_contract(self):
        c=client([tool_call(),{'content':json.dumps({'ok':True,'entity_id':'P1','name':'Nuit de Saïgon'})}])
        r=check_endpoint(c)
        self.assertTrue(r['passed']);self.assertEqual(c.attempts,2);self.assertIsNone(r['cost'])
        requests=[a.args[0] for a in c.opener.open.call_args_list]
        first,second=[json.loads(r.data) for r in requests]
        self.assertEqual(requests[0].get_header('Api-key'),'TEST_SECRET')
        self.assertEqual(first['model'],'deployment')
        self.assertIn('max_completion_tokens',first);self.assertNotIn('max_tokens',first)
        self.assertEqual(second['messages'][-1]['role'],'tool')
        self.assertEqual(second['response_format'],{'type':'json_object'})
        self.assertNotIn('TEST_SECRET',json.dumps(r))
        with self.assertRaises(ProviderError):c.chat([])
        self.assertEqual(c.opener.open.call_count,2)

    def test_wrong_tool_stops_before_second_call(self):
        m=tool_call();m['tool_calls'][0]['function']['name']='execute_shell'
        c=client([m])
        with self.assertRaises(ProviderError):check_endpoint(c)
        self.assertEqual(c.attempts,1)

    def test_unfaithful_or_non_json_final_fails(self):
        for answer in ['not JSON',json.dumps({'ok':True,'entity_id':'P1','name':'Invented'})]:
            c=client([tool_call(),{'content':answer}])
            with self.subTest(answer=answer),self.assertRaises(ProviderError):check_endpoint(c)

    def test_http_400_no_retry_or_secret_logging(self):
        c=client([])
        c.opener.open.side_effect=urllib.error.HTTPError(c.url,400,'bad request',{},None)
        with self.assertRaises(ProviderError) as e:c.chat([])
        self.assertIn('400',str(e.exception));self.assertNotIn('TEST_SECRET',str(e.exception))
        self.assertEqual(c.opener.open.call_count,1)
        self.assertEqual(c.calls[0]['error'],'http')

    def test_fail_fast_stops_remaining_conversation_turns(self):
        cases=json.loads((ROOT/'data/scenarios.json').read_text(encoding="utf-8"))
        case=next(c for c in cases if len(c['turns'])>1)
        c=client([]);c.opener.open.side_effect=urllib.error.HTTPError(c.url,400,'bad request',{},None)
        r=run_case(case,client=c,stop_on_provider_error=True)
        self.assertEqual(len(r['outputs']),1);self.assertFalse(r['auto_pass'])
        self.assertEqual(c.opener.open.call_count,1)

    def test_spacing_honors_deadline_without_request(self):
        c=client([]);c.min_interval_seconds=15;c.last_request_at=100
        with patch('ci_agentlab.providers.time.monotonic',return_value=101),self.assertRaises(ProviderError):
            c.chat([],timeout=10)
        self.assertEqual(c.attempts,0);self.assertEqual(c.opener.open.call_count,0)

    def test_agent_allows_longer_model_response_within_turn(self):
        from ci_agentlab.tools import Engine
        c=Mock();c.chat.return_value={'content':'{}'}
        e=Engine();e.deadline_seconds=180
        ToolAgent(c,e).turn('test')
        self.assertGreater(c.chat.call_args.kwargs['timeout'], 179)
        self.assertLessEqual(c.chat.call_args.kwargs['timeout'], 180)

    def test_timeout_retry_has_separate_attempt_and_total_budgets(self):
        clock=[0.0]; c=client([]); c.max_calls=3; c.min_interval_seconds=15
        good=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{}'}}], 'usage':{'prompt_tokens':1,'completion_tokens':1}}).encode())
        def open_request(req,timeout):
            if c.opener.open.call_count==1:
                self.assertEqual(timeout,60)
                clock[0]+=timeout
                raise TimeoutError('simulated')
            self.assertLessEqual(timeout,60)
            return good
        c.opener.open.side_effect=open_request
        def sleep(seconds):clock[0]+=seconds
        with patch('ci_agentlab.providers.time.monotonic',side_effect=lambda:clock[0]),patch('ci_agentlab.providers.time.sleep',side_effect=sleep),patch('ci_agentlab.providers.random.uniform',return_value=1):
            self.assertEqual(c.chat([],timeout=180)['content'],'{}')
        self.assertEqual(c.attempts,2)
        self.assertTrue(c.calls[0]['recovered_or_retried'])

    def test_timeout_retry_still_honors_global_deadline(self):
        clock=[0.0];c=client([]);c.max_calls=3
        def timeout(req,timeout):
            clock[0]+=timeout
            raise TimeoutError('simulated')
        c.opener.open.side_effect=timeout
        with patch('ci_agentlab.providers.time.monotonic',side_effect=lambda:clock[0]),patch('ci_agentlab.providers.time.sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch('ci_agentlab.providers.random.uniform',return_value=1):
            with self.assertRaises(ProviderError):c.chat([],timeout=60)
        self.assertEqual(c.attempts,1)

    def test_spacing_is_applied_to_next_request(self):
        c=client([{'content':'{}'}]);c.min_interval_seconds=15;c.last_request_at=100
        with patch('ci_agentlab.providers.time.monotonic',return_value=101),patch('ci_agentlab.providers.time.sleep') as sleep:
            c.chat([],timeout=30)
        sleep.assert_called_once_with(14)
        self.assertEqual(c.opener.open.call_args.kwargs['timeout'],16)

if __name__=='__main__':unittest.main()




