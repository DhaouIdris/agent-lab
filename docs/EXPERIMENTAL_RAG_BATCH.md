# Lot RAG de développement

Le lot `data/rag_batch_dev.json` comporte huit cas : quatre réponses présentes et quatre questions dont la réponse manque au corpus. L'état attendu et la grille humaine ne sont pas envoyés au modèle. Corpus et questions ont été rédigés ensemble : ce lot sert au diagnostic, pas à mesurer la généralisation.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_document_rag_batch.py -v
.\.venv\Scripts\python.exe -m experiments.document_rag_batch
```

Le programme demande la clé Azure en saisie masquée. Les appels sont séquentiels et respectent l'espacement du fichier `azure.json`. Il peut envoyer au plus 24 requêtes HTTP (8 cas × 3 tentatives, retries compris) ; chaque tentative peut être facturée. Sans correspondance lexicale, le cas s'abstient localement sans requête. Un incident fournisseur ou un JSON/citation invalide interrompt la campagne, en gardant les résultats déjà évalués dans `runs/rag_batch_.../report.json`. Un checkpoint est écrit après chaque cas ; une interruption pendant le premier cas peut ne pas produire de rapport. Les tokens rapportés peuvent être incomplets après une erreur ; `cost` reste null car aucune estimation de prix n'est implémentée.

Le rapport ne contient ni clé ni endpoint par construction ; il contient néanmoins questions, passages et réponses, qui nécessitent une revue avant partage. `campaign_complete: true` indique que tous les cas du lot ont été parcourus, pas qu'ils sont réussis. Les jugements automatiques portent seulement sur l'abstention déclarée et la présence d'un ID de passage attendu, lorsque le cas a une référence. Ils ne vérifient ni la fidélité du texte ni la pertinence de toutes les citations. `human_success_rate` reste null.

Lire chaque réponse, source et passage, notamment les quatre cas d'abstention, les affirmations impossibles à justifier et les faux refus. Un score élevé sur ce petit jeu ne constitue pas un benchmark indépendant. Étendre ensuite le corpus autorisé et construire des cas de test séparés avant comparaison de modèles ou de méthodes de retrieval.
