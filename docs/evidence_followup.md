# Vérification ciblée après la campagne de consistance

`data/audit_evidence_followup_3.json` reprend exactement trois questions de la campagne précédente, répétées trois fois en alternance : horaires du musée de Grand-Bassam, description de Taï avec demande de proximité, et référent manquant près d'un musée. Ce jeu est un suivi de développement sur les mêmes formulations, pas un nouveau jeu indépendant.

Depuis la racine du dépôt, sur une branche contenant l'arrêt des recherches sans preuve nouvelle :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/audit_evidence_followup_3.json --consistency --db local_data/lieux.sqlite --private-review
~~~

Neuf réponses nécessitent Azure ; aucun appel ORS n'est prévu. Le runner limite le budget à 45 tentatives fournisseur, retries compris. Les contrôles visent une citation UNESCO pour les deux questions documentaires, au plus une recherche pour Grand-Bassam, deux pour Taï et aucune pour la clarification. Ils vérifient aussi l'absence de certaines offres explicites de recherche de sites, de fiches musée, de lieux proches ou de documents officiels absents des outils. Ce contrôle lexical est volontairement étroit : un succès automatique ne prouve pas que toutes les promesses sont justes.

Comparer avec la campagne précédente les répétitions de ces trois mêmes IDs, leurs séquences d'outils, le nombre d'appels, les jetons et les latences. Relire **toutes** les réponses dans le fichier local `review.private.json`, y compris celles qui passent automatiquement. Une vérification humaine doit juger les promesses de capacité, la fidélité au passage cité et la précision du refus de proximité. L'ancien 36/36 et le nouveau résultat ne sont pas directement comparables sur les scores automatiques : ce suivi ajoute des contrôles et réduit le panel.

Le fichier `report.json` est conçu pour le partage ; conserver `review.private.json` localement pour la lecture des formulations et traces.
