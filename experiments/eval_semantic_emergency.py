"""Offline TF-IDF emergency classifier pilot; never used as a production guard."""
import argparse
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from experiments.request_controls import check_emergency_intent

def run(train_path,holdout_path):
    train=json.loads(Path(train_path).read_text(encoding='utf8'))
    hold=json.loads(Path(holdout_path).read_text(encoding='utf8'))
    if {x['id'] for x in train}&{x['id'] for x in hold}:raise ValueError('Overlapping case IDs')
    model=make_pipeline(TfidfVectorizer(analyzer='char',ngram_range=(2,5)),
                        LogisticRegression(class_weight='balanced',max_iter=1000,random_state=42))
    model.fit([x['question'] for x in train],[x['label']=='emergency' for x in train])
    scores=model.predict_proba([x['question'] for x in hold])[:,list(model.classes_).index(True)]
    results=[]
    for case,score in zip(hold,scores):
        semantic=bool(score>=0.5)
        results.append({'id':case['id'],'label':case['label'],'semantic':semantic,
                        'combined':semantic or check_emergency_intent(case['question'])})
    metrics={}
    for method in ('semantic','combined'):
        metrics[method]={key:sum((r['label']=='emergency')==actual and r[method]==pred
                            for r in results) for key,actual,pred in
                            [('tp',True,True),('fn',True,False),('fp',False,True),('tn',False,False)]}
    return {'kind':'development_semantic_emergency_comparison','threshold':0.5,
            'train_cases':len(train),'holdout_cases':len(hold),'metrics':metrics,'results':results,
            'caveat':'Tiny author-created train and holdout sets; no independent labels, calibrated probabilities, clinical validation or production safety guarantee.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--train',type=Path,default=Path('data/territory_controls_dev.json'))
    p.add_argument('--holdout',type=Path,default=Path('data/territory_emergency_holdout_40.json'))
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();report=run(args.train,args.holdout)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report['metrics'],ensure_ascii=False))

if __name__=='__main__':main()
