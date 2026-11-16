# Modèle de menace et contrôles v0.1

## Frontières de confiance

L'utilisateur, les documents, descriptions de lieux et sorties de fournisseurs externes peuvent contenir des instructions adverses. Le LLM propose des appels ; `Engine.call` décide s'ils sont exécutables. L'identité, les scopes, l'horloge et les autorisations proviennent de l'hôte.

Le laboratoire n'est pas un service d'authentification : `actor` et `scopes` sont fournis par le harness. En production, ils devront provenir d'une session authentifiée, jamais de champs contrôlés par le navigateur ou le LLM. Les événements `host_events` sont des événements de test de confiance, pas du texte de conversation.

## Matrice de permissions

| Outil | Effet | Autorisation | Confirmation |
|---|---|---|---|
| search_places | Lecture publique | Scope exact | Non |
| search_events | Lecture publique | Scope exact | Non |
| get_entity_details | Lecture publique | Scope exact | Non |
| search_knowledge | Lecture du corpus public | Scope exact | Non |
| plan_itinerary | Calcul de simulation | Scope exact | Non |
| get_booking_quote | Offre temporaire en mémoire | Scope exact, utilisateur courant | Non |
| create_simulated_booking | Création fictive | Scope + propriétaire de l'offre | Accord hôte sur l'offre exacte |
| get_simulated_booking | Lecture privée fictive | Scope + propriétaire | Non |
| cancel_simulated_booking | Annulation fictive | Scope + propriétaire | Accord hôte sur la réservation exacte |

L'accord est indexé par utilisateur, outil et arguments normalisés. Il expire et est consommé sous le même verrou que l'effet. Une offre conserve ses paramètres et n'est pas modifiable par l'outil de création. La réexécution de la même création retourne le résultat existant, après contrôle du propriétaire ; elle ne produit pas une deuxième réservation. L'annulation est également idempotente.

Ce verrou protège les threads d'un **seul processus**. Une version multi-instance devra utiliser des transactions et contraintes d'unicité en base, des autorisations persistantes, des clés d'idempotence durables et des garanties de concurrence adaptées. Aucun engagement de sécurité en production n'est déduit de ce verrou.

## Contrôles appliqués

- Neuf noms d'outils autorisés ; aucun shell, SQL libre, envoi d'email ou accès web arbitraire.
- Arguments stricts : champs supplémentaires refusés, bornes, dates avec fuseau, IDs limités, pas de coercition silencieuse des booléens en nombres.
- Inconnu et appartenant à un tiers renvoient tous deux `NOT_FOUND` pour les réservations.
- Huit appels d'outils par tour par défaut ; six tours modèle/outils ; trois tentatives identiques au maximum en cas d'erreur réessayable ; durée par tour de 60 secondes.
- Clés fournisseur absentes des prompts et des rapports ; en-têtes non journalisés ; redirections HTTP refusées ; HTTP distant non chiffré refusé.
- Validation des faits structurés contre les seules preuves réellement retournées, des IDs d'entités et de l'état des réservations.

## Limites explicites

Une attaque peut détourner une réponse textuelle sans modifier l'état. Il faut donc évaluer séparément les appels interdits proposés, les appels bloqués, les effets réellement exécutés et la réponse finale.

La validation structurée ne démontre pas la fidélité sémantique de `answer`. Un modèle peut omettre une affirmation du tableau `facts` et la placer dans le texte. La v0.1 signale les erreurs structurées dans le rapport mais n'est pas une interface publique avec filtrage complet. Une version produit devra rendre les champs critiques depuis des valeurs contrôlées, traiter les refus excessifs, assainir l'affichage et prévoir une politique de repli.

Les traces du pilote ne contiennent que des identités et réservations fictives. Avant des données réelles : minimisation, contrôle d'accès aux rapports, rétention, masquage des données personnelles et conformité applicable. Ne pas ajouter de secret ou de donnée privée dans les fixtures.

Les descriptions de source sont conservées comme données non fiables ; aucun filtre de mots-clés n'est présenté comme une protection complète. Les tests d'injection en replay valident les assertions attendues, pas la résistance d'un modèle réel.

## Référence

OWASP AI Agent Security Cheat Sheet, consultée le 16 novembre 2026 :
https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

Les contrôles sont une implémentation pédagogique limitée des principes de moindre privilège, autorisation hors modèle et confirmation liée à l'action. Ils ne constituent pas une certification OWASP.
