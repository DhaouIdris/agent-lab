"""Conservative lexical tripwire for retrieved documents, not a security boundary.

A match blocks the whole RAG request before model inference. Absence of a match
is not evidence that a document is safe; this is an experimental baseline.
"""
import re
import unicodedata


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))


# Require imperative/context combinations to avoid matching ordinary descriptions.
_PATTERNS = tuple(re.compile(p) for p in (
    r'\b(?:ignore|ignores|ignorer|ignorez|oublie|oubliez|oublier|disregard|forget|override)\b.{0,80}\b(?:instructions?|consignes?|regles?|directives?|prompts?|system|precedent(?:es?)?|previous|prior|above)\b',
    r'\b(?:reveal|print|send|leak|exfiltrate|disclose|reusable|affiche|revele|reveler|envoie|envoyer|divulgue|divulguer|transmets?)\b.{0,80}\b(?:secret|password|mot de passe|api.?key|cle(?:s)?|token|credential|identifiant)\b',
    r'\b(?:execute|executer|run|invoke|appelle|appeler|call|utilise|utiliser)\b.{0,60}\b(?:tool|outil|function|fonction|commande|command|shell|script)\b',
    r'\b(?:system|assistant|developer)\s*:\s*(?:ignore|reveal|execute|oublie|ignorez|revele)',
))


def inspect_passages(hits):
    """Check retrieved title and text; return IDs only, never suspicious text."""
    flagged = []
    for hit in hits:
        text = normalize(str(hit.get('title', '')) + '\n' + str(hit.get('text', '')))
        if any(p.search(text) for p in _PATTERNS):
            flagged.append(hit['id'])
    return flagged
