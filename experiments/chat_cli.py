"""Interactive terminal chat for the integrated agent; memory lives in this process only."""
import argparse
import re

from ci_agentlab.providers import ChatClient, ProviderError
from experiments.document_rag import load_corpus
from experiments.model_config import load_model_config
from experiments.model_credentials import model_key
from experiments.injection_guard import inspect_passages
from experiments.request_controls import redact_pii
from experiments.unified_agent import ask, AgentDiagnosticError

MAX_HISTORY=4
DIAGNOSTICS={
    'invalid_json':'Le modèle n’a pas renvoyé un objet JSON valide.',
    'invalid_object':'Le modèle a renvoyé un JSON qui n’est pas un objet.',
    'invalid_answer_or_abstain':'Champs answer ou abstain absents ou invalides.',
    'invalid_document_ids':'Le champ document_ids est absent ou invalide.',
    'invalid_place_ids':'Le champ place_ids est absent ou invalide.',
    'unobserved_document_ids':'La réponse cite un document non obtenu pendant ce tour.',
    'unobserved_place_ids':'La réponse cite un lieu non obtenu pendant ce tour.',
    'unsupported_price_or_time':'Un prix ou horaire affirmé n’est pas étayé.',
    'output_reference_guard':'Les références de la réponse ne passent pas le contrôle.',
}
HTTP_HINTS={401:'Clé API non acceptée.',403:'Accès refusé pour ce projet ou modèle.',
            404:'Modèle ou endpoint introuvable.',429:'Quota, crédits ou limite de débit à vérifier.'}


def provider_diagnostic(exc):
    metadata=exc.metadata
    status=metadata.get('http_status')
    code=metadata.get('provider_error_code')
    param=metadata.get('provider_error_param')
    if type(status) is int:
        detail=f'HTTP {status}'
        if code:detail+=' ; code='+code
        if param:detail+=' ; param='+param
        detail+=' — '+HTTP_HINTS.get(status,'Erreur de l’API du modèle.')
        return 'Diagnostic : provider_error — '+detail
    kind=metadata.get('provider_error_kind')
    return 'Diagnostic : provider_error'+(' — '+kind if kind else ' — appel interrompu avant une réponse exploitable')


def diagnostic_line(result):
    if result.get('guard_status')!='fallback_invalid_response':return None
    code=result.get('diagnostic_code') or 'unknown'
    details=result.get('diagnostic_metadata') or {}
    length=details.get('content_length')
    suffix=f' ({length} caractères reçus)' if type(length) is int else ''
    if details.get('finish_reason') in ('stop','length','tool_calls','content_filter','function_call'):
        suffix+=' ; fin='+details['finish_reason']
    if type(details.get('completion_tokens')) is int:
        suffix+=' ; tokens_sortie='+str(details['completion_tokens'])
    if type(details.get('reasoning_tokens')) is int:
        suffix+=' ; tokens_raisonnement='+str(details['reasoning_tokens'])
    return 'Diagnostic : '+code+' — '+DIAGNOSTICS.get(code,'Réponse rejetée par le validateur.')+suffix


def run_chat(client, db, docs, *, timeout=180, user_location=None, reader=input, writer=print, agent=ask, stream=False, write_chunk=None):
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
            if stream:writer('Recherche en cours…')
            result=agent(client,db,docs,question,timeout=timeout,user_location=user_location,history=history)
            answer=result['output']['answer']
            if stream and write_chunk is not None:
                write_chunk('Agent : ')
                for chunk in re.findall(r'\S+\s*|\s+',answer):write_chunk(chunk)
                write_chunk('\n')
            else:writer('Agent : '+answer)
            diagnostic=diagnostic_line(result)
            if diagnostic:writer(diagnostic)
            # Keep only safe, short context. Each new answer must fetch its own evidence.
            remember=(result.get('guard_status') in ('ambiguous_origin','activity_clarification') or
                      (result.get('guard_status') is None and not result['output'].get('abstain')))
            if remember and not inspect_passages([{'id':'answer','text':answer}]):
                history.append({'user':redact_pii(question)[:1000],
                                'assistant':redact_pii(answer)[:500]})
                del history[:-MAX_HISTORY]
        except (ValueError,ProviderError,AgentDiagnosticError) as exc:
            writer('Agent : Je ne peux pas répondre pour le moment. Cette question n’a pas été ajoutée au contexte.')
            if isinstance(exc,AgentDiagnosticError):
                if exc.code=='provider_error':writer(provider_diagnostic(exc))
                elif exc.code in ('invalid_tool_call_count','tool_budget_exceeded'):
                    count=exc.metadata.get('requested_tool_calls')
                    remaining=exc.metadata.get('remaining_tool_calls')
                    detail=(f' ({count} demandés ; {remaining} autorisés)' if type(count) is int and type(remaining) is int else '')
                    writer('Diagnostic : '+exc.code+detail)
                else:writer('Diagnostic : '+exc.code)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='local_data/lieux.sqlite')
    parser.add_argument('--corpus',default='data/rag_integrated_dev.json')
    parser.add_argument('--config',default='model.json')
    parser.add_argument('--user-location',nargs=2,type=float,metavar=('LAT','LON'))
    parser.add_argument('--stream',action='store_true',help='Affichage progressif du texte après validation du flux du modèle')
    args=parser.parse_args()
    try:
        config=load_model_config(args.config)
        key=model_key(config)
        docs=load_corpus(args.corpus)
        client=ChatClient(config['base_url'],config['deployment'],api_key=key,api_version=config.get('api_version'),
                          max_output_tokens=config['max_output_tokens'],max_calls=200,
                          auth_header=config['auth_header'],token_parameter=config['token_parameter'],
                          min_interval_seconds=config['min_interval_seconds'])
        if args.stream:
            client.stream=True
        run_chat(client,args.db,docs,timeout=config['turn_timeout_seconds'],user_location=args.user_location,
                 stream=args.stream,write_chunk=lambda part:print(part,end='',flush=True))
    except (OSError,ValueError) as exc:
        parser.exit(2,'Configuration ou données indisponibles : '+str(exc)+'\n')


if __name__=='__main__':main()
