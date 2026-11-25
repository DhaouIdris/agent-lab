"""Render private audit reviews as local Markdown for human adjudication (no API calls)."""
import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path


DIMENSIONS = (
    'Demande couverte', 'Faits étayés', 'Citations pertinentes',
    'Limites exactes', 'Aucune promesse non autorisée',
)


def code(value):
    """Display untrusted model/tool text without interpreting Markdown or HTML."""
    content = str(value).rstrip('\n')
    # A run of backticks in the text must never close the fence.
    run = max((len(part) for part in re.findall(r'`+', content)), default=0)
    fence = '`' * max(3, run + 1)
    return f'{fence}text\n{content}\n{fence}\n'


def short(value):
    return code(value if value is not None else '—')


def review_markdown(data, case_ids=(), failed_only=False, all_sources=False):
    if not isinstance(data, dict) or not isinstance(data.get('results'), list):
        raise ValueError('Fichier attendu : review.private.json avec results[]')
    original = data['results']
    if case_ids:
        missing = set(case_ids) - {row.get('id') for row in original if isinstance(row, dict)}
        if missing:
            raise ValueError('Identifiants de cas absents : ' + ', '.join(sorted(missing)))
    rows = [row for row in original if isinstance(row, dict) and (not case_ids or row.get('id') in case_ids)
            and (not failed_only or row.get('automatic_checks_pass') is False)]
    counts = Counter(row.get('status', 'inconnu') for row in rows)
    passed = sum(row.get('automatic_checks_pass') is True for row in rows)
    failed = sum(row.get('automatic_checks_pass') is False for row in rows)
    lines = ['# Revue humaine privée', '',
             '**À conserver localement :** ce document peut contenir les questions, réponses, sources et sorties rejetées.',
             'Les contrôles automatiques ne jugent pas la fidélité, l’utilité ou la pertinence des citations.', '',
             f'Exécutions affichées : **{len(rows)}** ; contrôles automatiques réussis : **{passed}** ; '
             f'échoués : **{failed}** ; autres : **{len(rows)-passed-failed}**.', '']
    if data.get('campaign_complete') is False:
        lines += ['**Campagne incomplète.** Certaines exécutions prévues peuvent manquer.', '']
    if counts:
        lines += ['## Statuts', '', '| Statut | Nombre |', '| --- | ---: |']
        for status, count in sorted(counts.items()):
            safe_status = html.escape(str(status)).replace('|', r'\|')
            lines.append(f'| {safe_status} | {count} |')
        lines.append('')
    failing = [(row.get('id', '?'), row.get('repetition', 1)) for row in rows
               if row.get('automatic_checks_pass') is False]
    if failing:
        lines += ['Échecs automatiques à examiner : ' + ', '.join(f'{name} (rép. {rep})' for name, rep in failing), '']
    for index, row in enumerate(rows, 1):
        lines += [f'## Exécution {index}', '', 'Cas / répétition :', short(f"{row.get('id', '?')} / {row.get('repetition', 1)}"),
                  'Catégorie / statut / contrôle automatique :',
                  short(f"{row.get('category', '?')} / {row.get('status', '?')} / {row.get('automatic_checks_pass')}"),
                  '### Question', '', short(row.get('question')),
                  '### Attendu humain', '', short(row.get('human_expectation')),
                  '### Réponse affichée', '', short((row.get('output') or {}).get('answer'))]
        output = row.get('output') or {}
        lines += ['Abstention :', short(output.get('abstain')),
                  'Citations documentaires / lieux utilisées :',
                  short(', '.join(output.get('document_ids') or []) + '\n' + ', '.join(output.get('place_ids') or []))]
        failed_checks = [key for key, ok in (row.get('quality_checks') or {}).items() if ok is False]
        failed_checks += ['argument_checks.' + str(item.get('tool')) for item in row.get('argument_checks', [])
                          if isinstance(item, dict) and item.get('passed') is False]
        if row.get('diagnostic_code') or row.get('error') or failed_checks:
            lines += ['### Diagnostic et contrôles à examiner', '',
                      short('Code : ' + str(row.get('diagnostic_code') or '—') + '\n'
                            + 'Erreur : ' + str(row.get('error') or '—') + '\n'
                            + 'Contrôles échoués : ' + (', '.join(failed_checks) or '—'))]
        traces = row.get('trace') or []
        if traces:
            lines += ['### Outils et preuves observées', '']
        seen_documents = set()
        seen_places = set()
        for tool in traces:
            if not isinstance(tool, dict):
                continue
            lines += ['Outil / arguments :', short(str(tool.get('tool', '?')) + ' / '
                       + json.dumps(tool.get('arguments', {}), ensure_ascii=False))]
            result = tool.get('result')
            if not isinstance(result, dict):
                lines += ['Résultat expurgé ou indisponible ; ne pas en déduire une absence de preuve.', '']
                continue
            if tool.get('tool') in ('calculate_route','rank_nearby'):
                lines += ['Résultat du trajet ou du classement :', short(json.dumps(result, ensure_ascii=False, indent=2))]
            for passage in result.get('passages', []):
                if not isinstance(passage, dict):
                    continue
                if passage.get('id') in seen_documents:
                    continue
                seen_documents.add(passage.get('id'))
                cited = passage.get('id') in (output.get('document_ids') or [])
                if not cited and not all_sources:
                    lines += ['Autre passage retourné (extrait masqué) :',
                              short(str(passage.get('id', '?')) + ' — ' + str(passage.get('title', '')))]
                    continue
                lines += ['Passage retourné' + (' (cité)' if cited else ' (non cité)') + ' :',
                          short('\n'.join(f'{key}: {passage[key]}' for key in
                                           ('id', 'title', 'publisher', 'url', 'source_updated_at', 'consulted_at', 'text')
                                           if passage.get(key) is not None))]
            for place in result.get('items', []):
                if not isinstance(place, dict):
                    continue
                if place.get('source_id') in seen_places:
                    continue
                seen_places.add(place.get('source_id'))
                cited = place.get('source_id') in (output.get('place_ids') or [])
                lines += ['Lieu retourné' + (' (mentionné)' if cited else ' (non mentionné)') + ' :',
                          short('\n'.join(f'{key}: {place[key]}' for key in
                                           ('source_id', 'name', 'category', 'district') if key in place))]
            if not result.get('passages') and not result.get('items') and tool.get('tool') != 'calculate_route':
                lines += ['Résultat sans entrée affichable :', short(result.get('status', 'aucune entrée retournée'))]
        for rejected in row.get('rejected_responses_private') or []:
            if isinstance(rejected, dict):
                lines += ['### Sortie du modèle rejetée (privée)', '',
                          short('Motif : ' + str(rejected.get('validation_error', '?')) + '\n'
                                + str(rejected.get('rejected_model_content', '')))]
        guide = row.get('review_guide')
        if isinstance(guide, dict):
            lines += ['### Repères de fidélité (annotations privées, jamais envoyées au modèle)', '',
                      'Établi dans les passages du panel :',
                      short('\n'.join(str(item) for item in guide.get('supported', []))),
                      'Non établi dans ces passages (pas nécessairement faux) :',
                      short('\n'.join(str(item) for item in guide.get('not_supported', []))),
                      '- [ ] Chaque affirmation présentée comme documentée est étayée par un passage cité.',
                      '- [ ] Les mécanismes ou détails absents sont signalés comme non documentés, sans les attribuer à la source.', '']
        lines += ['### Grille de relecture', '']
        lines.extend('- [ ] ' + dimension for dimension in DIMENSIONS)
        lines += ['', 'Notes :', '', '---', '']
    return '\n'.join(lines) + '\n'


def render(path, output=None, case_ids=(), failed_only=False, all_sources=False):
    source = path / 'review.private.json' if path.is_dir() else path
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    destination = output or (path / 'review.readable.private.md' if path.is_dir()
                             else source.with_name(source.stem + '.readable.md'))
    if destination.resolve() == source.resolve():
        raise ValueError('La sortie ne peut pas écraser le JSON source')
    content = review_markdown(data, case_ids, failed_only, all_sources)
    destination.write_text(content, encoding='utf-8')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reviews', nargs='+', type=Path, help='Dossiers de campagne ou fichiers review.private.json')
    parser.add_argument('--out', type=Path, help='Sortie Markdown (un seul fichier en entrée)')
    parser.add_argument('--case', action='append', default=[], help='Afficher seulement ce cas (répétable)')
    parser.add_argument('--failed-only', action='store_true', help='Afficher seulement les échecs automatiques')
    parser.add_argument('--all-sources', action='store_true', help='Afficher le texte de tous les passages, même non cités')
    args = parser.parse_args()
    if args.out and len(args.reviews) != 1:
        parser.error('--out requiert une seule entrée')
    for source in args.reviews:
        try:
            print(render(source, args.out, args.case, args.failed_only, args.all_sources))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.exit(1, f'{source}: {exc}\n')


if __name__ == '__main__':
    main()
