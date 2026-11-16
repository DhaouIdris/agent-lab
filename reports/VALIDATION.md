# Validation du premier lot — 16 novembre 2026

## Vérifié

- 48 tests automatisés `unittest` réussis sur Python 3.12.14 / Pydantic 2.13.4.
- 40 scénarios de développement validés : métadonnées, sources, règles de notation et comportements de référence.
- Trois replays de référence par scénario, soit 120 exécutions, acceptés par les vérificateurs.
- Schémas exportés : neuf entrées d'outils, une enveloppe de réponse, une réponse finale et un catalogue d'outils.
- Adaptateur HTTP testé avec une réponse simulée ; parcours agentique multi-tour de création/annulation testé avec un client simulé.

## Portée des tests

Confirmation falsifiée, mauvaise cible, autre utilisateur, expiration de l'offre et de l'accord, consommation de l'accord, vingt créations concurrentes d'une même offre, perte de réponse après création, annulation, bornes et types, rayon géographique, erreurs fournisseur, quotas d'appels, références inconnues, citations invalides, mauvais résultats volontairement injectés dans les replays et comparaison appariée.

## Non vérifié / non réalisé

- Aucun appel à un véritable LLM, endpoint Azure ou serveur local de l'utilisateur.
- Aucune performance de modèle mesurée, aucun classement, aucune preuve de résistance d'un LLM aux injections.
- Aucune validation indépendante des annotations par un annotateur humain.
- Aucune validation de production multi-instance, d'authentification réelle ou de disponibilité commerciale.
- Le corpus géographique reste minuscule et historique.

Les sorties détaillées du replay sont dans `reference/report.json`. Un score automatique de 100 % sur ces replays signifie que l'oracle reconnaît les comportements qu'il attend. Il ne doit pas être présenté comme un taux de réussite d'agent IA.
