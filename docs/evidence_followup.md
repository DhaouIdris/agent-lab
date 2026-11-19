# Vérification ciblée après la campagne de consistance

`data/audit_evidence_followup_3.json` reprend exactement trois questions de la campagne précédente, répétées trois fois en alternance : horaires du musée de Grand-Bassam, description de Taï avec demande de proximité, et référent manquant près d'un musée. Ce jeu est un suivi de développement sur les mêmes formulations, pas un nouveau jeu indépendant.

Depuis la racine du dépôt, sur une branche contenant l'arrêt des recherches sans preuve nouvelle :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/audit_evidence_followup_3.json --consistency --db local_data/lieux.sqlite --private-review
~~~

Neuf réponses nécessitent Azure ; aucun appel ORS n'est prévu. Le runner limite le budget à 45 tentatives fournisseur, retries compris. Les contrôles visent une citation UNESCO pour les deux questions documentaires, au plus une recherche pour Grand-Bassam, deux pour Taï et aucune pour la clarification. Ils vérifient aussi l'absence de certaines offres explicites de recherche de sites, de fiches musée, de lieux proches ou de documents officiels absents des outils. Ce contrôle lexical est volontairement étroit : un succès automatique ne prouve pas que toutes les promesses sont justes.

Comparer avec la campagne précédente les répétitions de ces trois mêmes IDs, leurs séquences d'outils, le nombre d'appels, les jetons et les latences. Relire **toutes** les réponses dans le fichier local `review.private.json`, y compris celles qui passent automatiquement. Une vérification humaine doit juger les promesses de capacité, la fidélité au passage cité et la précision du refus de proximité. L'ancien 36/36 et le nouveau résultat ne sont pas directement comparables sur les scores automatiques : ce suivi ajoute des contrôles et réduit le panel.

Le fichier `report.json` est conçu pour le partage ; conserver `review.private.json` localement pour la lecture des formulations et traces.

## Première campagne réelle du 19 novembre 2026

Sur la version initiale de ce panel, les neuf exécutions sont évaluables et six passent les contrôles automatiques. Les trois échecs sont les trois répétitions de `DIALOGUE-01` : chacune appelle `search_documents` deux fois, puis tente un troisième appel rejeté par le plafond. Elles prennent quatre appels fournisseur chacune. Les deux autres cas passent à chaque répétition. Le total est de 21 appels fournisseur et 48 450 jetons rapportés ; médiane 32,359 s et p95 empirique 61,546 s. Ces chiffres décrivent le seul échantillon, sans intervalle de généralisation.

La lecture des neuf réponses révèle aussi des écarts que les contrôles ne couvrent pas entièrement. Une réponse sur Taï attribue à ces caractéristiques la justification de son inscription UNESCO, lien causal absent de l'extrait cité. Les trois réponses à la question « près du musée » demandent utilement une précision, mais suggèrent parfois qu'un nom de musée permettrait une recherche utile dans le catalogue, qui ne contient pourtant pas de musées et ne classe pas par proximité. Ce constat vient d'une analyse de développement par l'assistant, pas d'une annotation humaine indépendante. Un contrôle lexical plus précis repère désormais l'offre explicite « je lancerai la recherche par nom du musée » ; les implicites restent soumis à revue.

La modification consécutive retire l'outil documentaire après deux recherches distinctes tout en laissant l'outil catalogue disponible pour une éventuelle demande mixte. Elle précise dans le prompt qu'un nom de musée ne suffit pas à une recherche de proximité. La première campagne ne mesure pas cette modification : refaire le panel sur la nouvelle révision, puis comparer appels, jetons, temps et qualité des neuf réponses avant toute conclusion de gain.
