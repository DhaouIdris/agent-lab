"""Opt-in hybrid retrieval: local BM25 + remote Azure embeddings + RRF.

This experimental CLI sends question and corpus to Azure; it makes one request,
uses no local model weights, and never generates an answer.
"""
import argparse
import getpass
import json
import math
import os
import urllib.request
from urllib.parse import urlsplit
from experiments.document_rag import load_corpus, retrieve
from experiments.prompt_shield import _NoRedirect


def rrf(lexical, semantic, k=3, constant=60):
    if type(k) is not int or not 1 <= k <= 10:
        raise ValueError('k must be 1..10')
    scores = {}
    for ranking in (lexical, semantic):
        if len(ranking) != len(set(ranking)):
            raise ValueError('Duplicate ID in ranking')
        for rank, identifier in enumerate(ranking, 1):
            scores[identifier] = scores.get(identifier, 0) + 1 / (constant + rank)
    return sorted(scores, key=lambda identifier: (-scores[identifier], identifier))[:k]


def cosine(a, b):
    if not a or len(a) != len(b) or any(type(v) not in (int, float) or not math.isfinite(v) for v in a+b):
        raise ValueError('Invalid vectors')
    norm_a = math.sqrt(sum(v*v for v in a)); norm_b = math.sqrt(sum(v*v for v in b))
    if not norm_a or not norm_b:
        raise ValueError('Zero vector')
    return sum(x*y for x,y in zip(a,b)) / (norm_a*norm_b)


def embeddings(endpoint, key, deployment, texts, opener=None):
    p = urlsplit(endpoint)
    host = (p.hostname or '').lower()
    if (p.scheme != 'https' or p.username or p.password or p.port not in (None,443)
            or not host.endswith(('.openai.azure.com','.cognitiveservices.azure.com'))
            or p.path.rstrip('/') != '/openai/v1' or p.query or p.fragment or not key or not deployment):
        raise ValueError('Invalid Azure embedding endpoint or credentials')
    if not 1 <= len(texts) <= 101 or any(not isinstance(t,str) or not t.strip() for t in texts):
        raise ValueError('Expected 1..101 nonempty inputs')
    req = urllib.request.Request('https://' + host + '/openai/v1/embeddings',
        data=json.dumps({'model':deployment,'input':texts},ensure_ascii=False).encode('utf8'),
        headers={'Content-Type':'application/json','api-key':key},method='POST')
    try:
        with (opener or urllib.request.build_opener(_NoRedirect())).open(req,timeout=60) as resp:
            obj=json.loads(resp.read(16*1024*1024).decode('utf8'))
        rows=obj['data']
        if not isinstance(rows,list) or len(rows)!=len(texts):raise ValueError()
        indexed={}
        for row in rows:
            index=row['index']; vector=row['embedding']
            if type(index) is not int or not 0<=index<len(texts) or index in indexed or not isinstance(vector,list):raise ValueError()
            indexed[index]=vector
        vectors=[indexed[i] for i in range(len(texts))]
        for vector in vectors:cosine(vectors[0],vector)
        return vectors
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, OverflowError):
        raise RuntimeError('Embedding request failed or returned invalid vectors') from None


def hybrid(question, docs, vectors, k=3, candidate_limit=10):
    if len(vectors)!=len(docs)+1:raise ValueError('Embedding count does not match corpus')
    lexical=[x['id'] for x in retrieve(question,docs,k=min(10,candidate_limit))]
    semantic=sorted(((cosine(vectors[0], v),d['id']) for d,v in zip(docs,vectors[1:])),key=lambda x:(-x[0],x[1]))
    ids=rrf(lexical,[i for _,i in semantic[:candidate_limit]],k=k)
    by_id={d['id']:d for d in docs}
    return {'passages':[by_id[i] for i in ids], 'lexical_ids':lexical,
            'semantic_ids':[i for _,i in semantic[:candidate_limit]], 'method':'bm25_cosine_rrf',
            'caveat':'Experimental retrieval only; no relevance threshold or generation; evaluate before use.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',required=True);p.add_argument('--question',required=True)
    p.add_argument('--endpoint',required=True,help='Azure resource base ending in /openai/v1')
    p.add_argument('--deployment',required=True,help='Azure embedding deployment name')
    p.add_argument('--k',type=int,default=3)
    a=p.parse_args();docs=load_corpus(a.corpus)
    if not a.question.strip() or len(a.question)>2000:p.error('Question must contain 1..2000 characters')
    if not 1<=a.k<=10:p.error('k must be 1..10')
    if len(docs)>100:p.error('Experimental limit: maximum 100 passages')
    key=os.getenv('AGENTLAB_API_KEY') or getpass.getpass('Clé Azure (saisie masquée) : ')
    vectors=embeddings(a.endpoint,key,a.deployment,[a.question]+[d['title']+'\n'+d['text'] for d in docs])
    print(json.dumps(hybrid(a.question,docs,vectors,k=a.k),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
