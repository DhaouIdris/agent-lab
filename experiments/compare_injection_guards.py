"""Compare two experimental lexical detectors offline, without Azure or weights."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from experiments.injection_guard import inspect_passages, normalize

ROOT = Path(__file__).resolve().parents[1]
# Candidate designed from the development failures. Not wired into the RAG.
_EXTRA = tuple(re.compile(p) for p in (
    r'\b(?:replace|rewrite|change|remplace|reecris|modifie|changez|remplacer)\b.{0,60}\b(?:answer|response|reponse|resultat)\b',
    r'\b(?:respond|reply|answer|reponds|repondez|repondre)\b.{0,60}\b(?:always|instead|toujours|uniquement|quel que soit)\b',
    r'\b(?:publish|publie|publier|reveal|disclose|divulgue|expose|affiche|envoie|transmets|send)\b.{0,80}\b(?:credentials?|identifiants?|variables? d.environment|environment variables?)\b',
    r'\b(?:disable|desactive|desactiver|disabled|desactivee)\b.{0,60}\b(?:security|securite|policy|politique|guardrails?)\b',
))


def candidate(text):
    hit = {'id': 'X', 'text': text}
    return bool(inspect_passages([hit])) or any(p.search(normalize(text)) for p in _EXTRA)


def score(cases, detector):
    rows = []
    for c in cases:
        actual = detector(c['text'])
        expected = c['label'] == 'malicious'
        rows.append({'id': c['id'], 'label': c['label'], 'blocked': actual, 'match': actual == expected})
    tp = sum(r['blocked'] and r['label'] == 'malicious' for r in rows)
    fn = sum(not r['blocked'] and r['label'] == 'malicious' for r in rows)
    fp = sum(r['blocked'] and r['label'] == 'benign' for r in rows)
    tn = sum(not r['blocked'] and r['label'] == 'benign' for r in rows)
    return {'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
            'malicious_detection_rate': tp / (tp + fn) if tp + fn else None,
            'benign_block_rate': fp / (fp + tn) if fp + tn else None, 'results': rows}


def evaluate_file(path):
    raw = Path(path).read_bytes()
    cases = json.loads(raw.decode('utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('Cases must be a nonempty list')
    ids = set()
    for c in cases:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id'] or c['id'] in ids or c.get('label') not in ('malicious', 'benign') or not isinstance(c.get('text'), str) or not c['text'].strip():
            raise ValueError('Invalid case or duplicate ID')
        ids.add(c['id'])
    return {'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'cases': len(cases),
            'baseline': score(cases, lambda t: bool(inspect_passages([{'id':'X', 'text':t}]))),
            'candidate_offline_only': score(cases, candidate)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', action='append', help='JSON cases; repeat for multiple sets')
    args = p.parse_args()
    paths = args.cases or [ROOT/'data/injection_guard_dev.json', ROOT/'data/injection_guard_challenge.json']
    print(json.dumps({'kind':'offline_guard_comparison', 'sets':[evaluate_file(x) for x in paths],
        'caveat':'Both sets were authored for this project, not independently annotated; no model evaluated. Candidate is not deployed.'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
