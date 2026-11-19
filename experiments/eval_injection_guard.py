"""Offline diagnostic for the experimental tripwire; no provider or model used."""
import json
from pathlib import Path
from experiments.injection_guard import inspect_passages


def evaluate(cases):
    rows = []
    for case in cases:
        predicted = bool(inspect_passages([{'id': case['id'], 'text': case['text']}]))
        expected = case['label'] == 'malicious'
        rows.append({'id': case['id'], 'label': case['label'], 'blocked': predicted,
                     'match': predicted == expected})
    tp = sum(r['blocked'] and r['label'] == 'malicious' for r in rows)
    fn = sum(not r['blocked'] and r['label'] == 'malicious' for r in rows)
    fp = sum(r['blocked'] and r['label'] == 'benign' for r in rows)
    tn = sum(not r['blocked'] and r['label'] == 'benign' for r in rows)
    return {'kind': 'experimental_guard_development_only', 'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
            'malicious_detection_rate': tp / (tp + fn) if tp + fn else None,
            'benign_block_rate': fp / (fp + tn) if fp + tn else None,
            'results': rows,
            'caveat': 'Author-created examples, not independent. Does not prove safety or evaluate a model.'}


def main():
    cases = json.loads(Path('data/injection_guard_dev.json').read_text(encoding='utf-8'))
    print(json.dumps(evaluate(cases), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
