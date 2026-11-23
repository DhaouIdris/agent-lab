"""Render a benchmark manifest as a reviewable Markdown document, without calls."""
import argparse
from collections import Counter
from pathlib import Path

from experiments.audit_campaign import load_cases
from experiments.readable_review import code


def render_cases(cases):
    counts=Counter(c['category'] for c in cases)
    lines=['# Questions pour revue avant la campagne', '',
           'Les questions sont montrées telles que l’utilisateur les poserait. Les attentes et les étiquettes sont des annotations du benchmark, jamais envoyées au modèle.',
           '',f'**{len(cases)} scénarios, {sum(c["consistency"] for c in cases)} sélectionnés pour trois répétitions.**','',
           '| Catégorie | Cas | Répétitions |','| --- | ---: | ---: |']
    for category in sorted(counts):
        lines.append(f'| {category} | {counts[category]} | {sum(c["category"]==category and c["consistency"] for c in cases)} |')
    for category in dict.fromkeys(c['category'] for c in cases):
        lines.extend(['',f'## {category.capitalize()}',''])
        for case in (c for c in cases if c['category']==category):
            lines.extend([f'### {case["id"]}'+(' · répété 3 fois' if case['consistency'] else ''),
                          '', '**Question**', '',code(case['question']),
                          '**À vérifier humainement**', '',code(case['human_expectation'])])
    return '\n'.join(lines)+'\n'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=Path,default=Path('data/agent_holdout_natural_52.json'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    if a.out.exists():p.error('Output file already exists')
    content=render_cases(load_cases(a.cases,False))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(content,encoding='utf-8')
    print(a.out)


if __name__=='__main__':main()
