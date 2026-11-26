"""Interactive terminal chat for the integrated agent; memory lives in this process only."""
import argparse

from ci_agentlab.providers import ChatClient, ProviderError
from experiments.document_rag import load_corpus
from experiments.model_config import load_model_config
from experiments.model_credentials import model_key
from experiments.injection_guard import inspect_passages
from experiments.request_controls import redact_pii
from experiments.unified_agent import ask, AgentDiagnosticError

MAX_HISTORY=4


def run_chat(client, db, docs, *, timeout=180, user_location=None, reader=input, writer=print, agent=ask):
    history=[]
    writer('Chat prêt. /reset efface le contexte ; /quit termine la session.')
    while True:
        try:question=reader('Vous : ')
        except (EOFError,KeyboardInterrupt):
            writer('\nFin de session.')
            return
        if question.strip().casefold() in ('/quit','/exit'):
            writer('Fin de session.')
            return
        if question.strip().casefold()=='/reset':
            history.clear();writer('Contexte effacé.');continue
        if not question.strip():continue
        try:
            result=agent(client,db,docs,question,timeout=timeout,user_location=user_location,history=history)
            answer=result['output']['answer']
            writer('Agent : '+answer)
            # Keep only safe, short context. Each new answer must fetch its own evidence.
            if result.get('guard_status') is None and not result['output'].get('abstain') and not inspect_passages([{'id':'answer','text':answer}]):
                history.append({'user':redact_pii(question)[:1000],
                                'assistant':redact_pii(answer)[:500]})
                del history[:-MAX_HISTORY]
        except (ValueError,ProviderError,AgentDiagnosticError) as exc:
            writer('Agent : Je ne peux pas répondre pour le moment. Cette question n’a pas été ajoutée au contexte.')
            if isinstance(exc,AgentDiagnosticError):
                writer('Diagnostic : '+exc.code)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='local_data/lieux.sqlite')
    parser.add_argument('--corpus',default='data/rag_integrated_dev.json')
    parser.add_argument('--config',default='model.json')
    parser.add_argument('--user-location',nargs=2,type=float,metavar=('LAT','LON'))
    args=parser.parse_args()
    try:
        config=load_model_config(args.config)
        key=model_key(config)
        docs=load_corpus(args.corpus)
        client=ChatClient(config['base_url'],config['deployment'],api_key=key,api_version=config.get('api_version'),
                          max_output_tokens=config['max_output_tokens'],max_calls=200,
                          auth_header=config['auth_header'],token_parameter=config['token_parameter'],
                          min_interval_seconds=config['min_interval_seconds'])
        run_chat(client,args.db,docs,timeout=config['turn_timeout_seconds'],user_location=args.user_location)
    except (OSError,ValueError) as exc:
        parser.exit(2,'Configuration ou données indisponibles : '+str(exc)+'\n')


if __name__=='__main__':main()
