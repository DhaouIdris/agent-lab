"""Offline author-created lexical emergency tripwire check; no model or network calls."""
import argparse
import json
from pathlib import Path

from experiments.request_controls import check_emergency_intent


def evaluate(path):
    cases=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cases,list) or any(c.get('label') not in ('emergency','benign') for c in cases):
        raise ValueError('Invalid cases')
    results=[{'id':c['id'],'label':c['label'],'blocked':check_emergency_intent(c['question'])} for c in cases]
    tp=sum(r['label']=='emergency' and r['blocked'] for r in results)
    fn=sum(r['label']=='emergency' and not r['blocked'] for r in results)
    fp=sum(r['label']=='benign' and r['blocked'] for r in results)
    tn=sum(r['label']=='benign' and not r['blocked'] for r in results)
    return {'kind':'development_lexical_emergency_only','tp':tp,'fn':fn,'fp':fp,'tn':tn,
            'recall':tp/(tp+fn) if tp+fn else None,
            'benign_block_rate':fp/(fp+tn) if fp+tn else None,'results':results,
            'caveat':'Author-created small panel; no independent labels, latency claim, classifier or safety guarantee.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,default=Path('data/territory_controls_dev.json'))
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    report=evaluate(args.cases)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(args.out)


if __name__=='__main__':main()
