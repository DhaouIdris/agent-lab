"""Deterministic output boundaries for optional official-feed mode.

IDs and URLs are checked mechanically. Claim-level factual support still needs review.
"""
import re


_CIT = re.compile(r'\[CIT:([A-Za-z0-9_./:-]{1,120})\]')
_HANDOFF = re.compile(r'\[\[HANDOFF:([A-Za-z0-9_-]{1,120})\]\]')
_URL = re.compile(r'(?i)\b(?:https?://|www\.)\S+')
_RULE_QUESTION = re.compile(r'\b(?:passeport|visa|permis|taxe|eligibilite|formalite|dossier|residence|titre de sejour|zfe)\b',re.I)


def verify_and_render(answer: str, document_ids: list[str], observed_evidence: dict,
                      handoffs: dict[str,str], question: str, abstain: bool) -> str:
    """Reject invented references, unsourced regulatory answers and arbitrary URLs.

    ``handoffs`` must be an application-owned allowlist, never a model/tool text field.
    """
    if _URL.search(answer):
        raise ValueError('Untrusted URL in model output')
    cited=set(_CIT.findall(answer))
    if not cited <= set(document_ids) or not cited <= set(observed_evidence):
        raise ValueError('Invented inline citation')
    if not abstain and _RULE_QUESTION.search(question) and not cited:
        raise ValueError('Regulatory answer without inline evidence')
    used=set(_HANDOFF.findall(answer))
    if not used<=set(handoffs):
        raise ValueError('Unknown handoff ID')
    def citation(match):
        evidence=observed_evidence[match.group(1)]
        title=evidence.get('title') or evidence.get('publisher') or 'Source'
        updated=evidence.get('updated_at')
        return f'[{title}'+(f', mise à jour {updated}' if updated else ', date non renseignée')+']'
    rendered=_CIT.sub(citation,answer)
    rendered=_HANDOFF.sub(lambda m:handoffs[m.group(1)],rendered)
    return rendered
