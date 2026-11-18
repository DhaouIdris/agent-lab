"""Compare local BM25 and hybrid ranking with one opt-in Azure embedding call."""
import argparse
import getpass
import hashlib
import json
import os
import time
from pathlib import Path
from experiments.document_rag import load_corpus, retrieve
from experiments.hybrid_retrieval import embeddings, hybrid


def run(docs, cases, vectors, k=3):
    if len(vectors) != len(docs)+len(cases):raise ValueError('Embedding count mismatch')
    ids={d['id'] for d in docs};rows=[];document_vectors=vectors[:len(docs)]
    for case, query in zip(cases,vectors[len(docs):]):
        relevant=case['relevant_ids']
        if not set(relevant)<=ids:raise ValueError('Unknown relevant passage')
        lexical=[d['id'] for d in retrieve(case['question'],docs,k=k)]
        fused=[d['id'] for d in hybrid(case['question'],docs,[query]+document_vectors,k=k)['passages']]
        row={'id':case['id'], 'labelled_answerable':bool(relevant)}
        for name, ranked in [('bm25',lexical),('hybrid',fused)]:
            hits=len(set(ranked)&set(relevant))
            row[name]={'returned_ids':ranked,'hit_at_k':bool(hits) if relevant else None,
                       'recall_at_k':hits/len(relevant) if relevant else None,
                       'returned_any':bool(ranked)}
        rows.append(row)
    metrics={}
    for name in ('bm25','hybrid'):
        labelled=[r[name] for r in rows if r['labelled_answerable']]
        unlabelled=[r[name] for r in rows if not r['labelled_answerable']]
        metrics[name]={'labelled_cases':len(labelled),
            'hit_at_k':sum(x['hit_at_k'] for x in labelled)/len(labelled) if labelled else None,
            'recall_at_k':sum(x['recall_at_k'] for x in labelled)/len(labelled) if labelled else None,
            'unanswerable_cases':len(unlabelled),'unanswerable_with_any_returned':sum(x['returned_any'] for x in unlabelled)}
    return {'results':rows,'metrics':metrics}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',default='data/rag_seed_extended.json');p.add_argument('--cases',default='data/rag_challenge_dev.json')
    p.add_argument('--endpoint',required=True);p.add_argument('--deployment',required=True)
    p.add_argument('--out',required=True);p.add_argument('--k',type=int,default=3)
    a=p.parse_args();out=Path(a.out)
    if out.exists():p.error('Output exists; choose a new path')
    if not 1<=a.k<=10:p.error('k must be 1..10')
    docs=load_corpus(a.corpus);raw=Path(a.cases).read_bytes();cases=json.loads(raw.decode('utf8'))
    if not isinstance(cases,list) or not cases or len(docs)+len(cases)>101:p.error('Need 1..101 combined passages and questions')
    if any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not isinstance(c.get('question'),str) or not c['question'].strip() or len(c['question'])>2000 or not isinstance(c.get('relevant_ids'),list) or any(not isinstance(x,str) for x in c['relevant_ids']) or len(c['relevant_ids'])!=len(set(c['relevant_ids'])) for c in cases):p.error('Invalid case metadata')
    if len({c['id'] for c in cases})!=len(cases) or any(not set(c['relevant_ids'])<={d['id'] for d in docs} for c in cases):p.error('Duplicate IDs or unknown relevant passage')
    key=os.getenv('AGENTLAB_API_KEY') or getpass.getpass('Clé Azure embeddings (saisie masquée) : ')
    texts=[d['title']+'\n'+d['text'] for d in docs]+[c['question'] for c in cases]
    start=time.monotonic()
    try:
        vectors=embeddings(a.endpoint,key,a.deployment,texts)
    except RuntimeError:
        with out.open('x',encoding='utf8') as f:
            json.dump({'kind':'development_hybrid_comparison','campaign_complete':False,
                       'provider_attempts':1,'error':'embedding_provider_unavailable_or_invalid_response'},f,indent=2)
        p.exit(1,'Appel embeddings indisponible ou réponse invalide ; rapport partiel enregistré.\n')
    elapsed=time.monotonic()-start
    report=run(docs,cases,vectors,k=a.k)
    report['campaign_complete']=True
    report.update(kind='development_hybrid_comparison',cases_sha256=hashlib.sha256(raw).hexdigest(),
      corpus_sha256=hashlib.sha256(Path(a.corpus).read_bytes()).hexdigest(),k=a.k,provider_attempts=1,
      embedding_call_seconds=round(elapsed,3),cost=None,usage=None,
      caveat='Development labels not independent. One embedding request contains all questions and passages; no generation, cache, usage or cost measurement. Empty labels do not prove every returned passage irrelevant.')
    with out.open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'output':out.name,'metrics':report['metrics'],'embedding_call_seconds':report['embedding_call_seconds']},ensure_ascii=False))


if __name__=='__main__':main()
