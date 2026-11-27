"""Small provider compatibility probe with fixed harmless inputs and redacted output."""
import argparse
import json

from ci_agentlab.providers import ChatClient, ProviderError
from experiments.model_config import load_model_config
from experiments.model_credentials import model_key

TOOL={'type':'function','function':{'name':'echo_probe','description':'Echo a test value.',
      'parameters':{'type':'object','properties':{'value':{'type':'string'}},
                    'required':['value'],'additionalProperties':False}}}


def probe(client):
    prompts=[('json_only',[], 'auto'),
             ('tool_auto',[TOOL],'auto'),
             ('tool_forced',[TOOL],{'type':'function','function':{'name':'echo_probe'}})]
    results=[]
    for stage,tools,choice in prompts:
        messages=[{'role':'system','content':'This is a format test. Reply in JSON. For tool stages call echo_probe with value test.'},
                  {'role':'user','content':'Return {"ok":true} or call the offered tool.'}]
        try:
            reply=client.chat(messages,timeout=45,tools_override=tools,tool_choice=choice,
                              response_format={'type':'json_object'})
        except ProviderError:
            last=client.calls[-1] if client.calls else {}
            results.append({'stage':stage,'status':'provider_error',
                            **{k:last[k] for k in ('http_status','provider_error_code','provider_error_param','error_kind') if k in last}})
            break
        calls=reply.get('tool_calls') or []
        content=reply.get('content')
        try:valid_json=isinstance(json.loads(content),dict) if isinstance(content,str) else False
        except ValueError:valid_json=False
        results.append({'stage':stage,'status':'ok','valid_json_object':valid_json,
                        'tool_call_names':[c.get('function',{}).get('name') for c in calls if isinstance(c,dict)]})
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default='model.json')
    a=p.parse_args();cfg=load_model_config(a.config)
    client=ChatClient(cfg['base_url'],cfg['deployment'],api_key=model_key(cfg),api_version=cfg.get('api_version'),
        max_output_tokens=cfg['max_output_tokens'],max_calls=5,auth_header=cfg['auth_header'],
        token_parameter=cfg['token_parameter'],min_interval_seconds=cfg['min_interval_seconds'])
    print(json.dumps(probe(client),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
