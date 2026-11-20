"""Experimental input-only lexical guard; not a complete security boundary."""
import re
import unicodedata
from experiments.injection_guard import inspect_passages, normalize

# Signals require a requested behavior and an instruction/secret target or a
# strong override/impersonation context. They can still cause false positives.
_PATTERNS=tuple(re.compile(p,re.DOTALL) for p in (
    r'\b(?:revel\w*|divulgu\w*|affich\w*|montr\w*|fourn\w*|repete\w*|envoi\w*|transmet\w*|expose\w*|reveal\w*|disclos\w*|show|send)\b.{0,100}\b(?:(?:tes?|vos?|your)\s+)?(?:instructions?\s+(?:systeme?|internes?)|consignes?\s+internes?|prompt\s+(?:systeme?|interne)|message\s+initial\s+cache|configuration\s+secrete|identifiants?|credentials?|environment\s+variables?|variables?\s+d.environnement|variables?\s+d.environment)\b',
    r'\b(?:traite\w*|consider\w*|treat|regard)\b.{0,100}\b(?:mon\s+message|this\s+message|my\s+message)\b.{0,80}\b(?:systeme?|system|prioritaire|priority|developer)\b',
    r'\b(?:securite|security|guardrails?|controls?|controle|verification)\b.{0,60}\b(?:suspend\w*|desactiv\w*|contourn\w*|disabled|bypass\w*)\b.{0,80}\b(?:affirme\w*|repond\w*|obey|answer|fourn\w*|pretend\w*)\b',
    r'\b(?:desactiv\w*|contourn\w*|passe\s+outre|disable\w*|bypass\w*)\b.{0,60}\b(?:securite|security|guardrails?|controls?|controle|consignes?|regles?|policies)\b',
    r'\b(?:obeis|obeissez|obey|suis|follow)\b.{0,90}\b(?:nouvelles?\s+regles?|new\s+rules?|mes\s+regles?)\b.{0,100}\b(?:precedent\w*|previous|prior|systeme?|instead|lieu)\b',
    r'\b(?:remplace\w*|reecri\w*|modifi\w*|replace\w*|rewrite\w*)\b.{0,60}\b(?:ta\s+|la\s+|the\s+)?(?:reponse|answer|response|resultat)\b.{0,40}\b(?:par|en|avec|with|to\s+say)\b',
    r'\b(?:ne\s+respecte\w*\s+plus|ignore\w*|oublie\w*|disregard\w*)\b.{0,70}\b(?:consignes?|instructions?|regles?|directives?|policies|instructions)\b',
    r'\b(?:pretends?|pretendez|pretend|fais\s+semblant)\b.{0,90}\b(?:verifi\w*|confirm\w*|checked|verified)\b.{0,80}\b(?:meme\s+si|without|sans\s+avoir|pas\s+le\s+cas)\b',
    r'\b(?:ne\s+utilise\w*\s+pas|n.utilise\w*\s+pas|do\s+not\s+use)\b.{0,50}\b(?:sources?|evidence)\b.{0,80}\b(?:invent\w*|fabricat\w*|make\s+up)\b',
))

def inspect_user_input(text):
    """Return a boolean; do not retain input or expose rule matches."""
    text=''.join(c for c in text if unicodedata.category(c)!='Cf')
    text=normalize(text)
    # Compact a small set of spaced-letter override verbs, not arbitrary text.
    text=re.sub(r'\bi\s+g\s+n\s+o\s+r\s+e\b','ignore',text)
    # Disambiguate public entity IDs and formatting requests at phrase level.
    # Other instructions in the same input are still scanned.
    text=re.sub(r"\bidentifiants?(?:\s+publics?)?\s+(?:(?:des?|du)\s+(?:(?:deux|trois|ces)\s+)?(?:glaciers?|cafes?|restaurants?|hotels?|lieux|catalogue)\b|osm\b)", "references catalogue ", text)
    text=re.sub(r"\b(?:un\s+)?identifiant\s+public\s+(?:osm|openstreetmap)\b", "reference catalogue", text)
    text=re.sub(r"\b(?:remplace|reecris|modifie) (?:ta|la) reponse (?:par|en) (?:une liste|un tableau|deux phrases)\b", "presente au format demande ", text)
    # A separate explanation clause can mention a secret without requesting it.
    # Inspect each clause independently; a malicious imperative in either still blocks.
    clauses=re.split(r'\b(?:et|puis)\s+(?=explique\w*\b)',text)
    return any(bool(inspect_passages([{'id':'user','text':clause}])) or any(p.search(clause) for p in _PATTERNS)
               for clause in clauses)
