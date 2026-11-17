# RAG documentaire expérimental

Cette chaîne expérimentale est séparée de l'agent à outils et du catalogue SQLite. Elle ne les remplace pas. Six annotations factuelles rédigées pour le projet résument des pages UNESCO, SIREXE et CEPICI ; ce ne sont ni des extraits verbatim ni une copie complète des documents. Les liens, éditeurs, dates de consultation, date de mise à jour de la source quand elle est connue, et type de contenu sont enregistrés dans `data/rag_seed.json`. Les dates de consultation ne garantissent ni fraîcheur ni exhaustivité.

## Fonctionnement

1. Le corpus figé est chargé depuis JSON. Chaque annotation est traitée comme un passage ; il n'y a pas encore d'extracteur HTML/PDF ni de découpage automatique de documents.
2. Une recherche lexicale BM25, en mémoire et sans GPU, ordonne les passages ; aucun modèle d'embedding ou service vectoriel n'est requis.
3. Pour `ask`, les passages sont envoyés au modèle Azure. Il produit un JSON avec réponse, indicateurs d'abstention et identifiants de citations. Les IDs cités sont vérifiés contre les seuls passages retournés ; l'exactitude de la réponse et la pertinence sémantique des citations ne sont pas garanties.
4. Une recherche sans aucun terme correspondant s'abstient sans appeler Azure. Une correspondance lexicale n'est pas une preuve de pertinence : une question hors périmètre peut retourner des passages sans réponse ; le modèle doit alors s'abstenir, ce qui nécessite une évaluation humaine.

## Essais PowerShell

À la racine du dépôt et dans l'environnement virtuel déjà configuré :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_document_rag.py -v
.\.venv\Scripts\python.exe -m experiments.document_rag eval
.\.venv\Scripts\python.exe -m experiments.document_rag retrieve --question "En quelle année Grand-Bassam a-t-elle été inscrite ?"
.\.venv\Scripts\python.exe -m experiments.document_rag ask --question "En quelle année Grand-Bassam a-t-elle été inscrite ?"
```

`eval` et `retrieve` sont locaux ; `ask` requiert le `azure.json` et la clé déjà utilisés, et peut entraîner jusqu'à trois tentatives facturables, sauf s'il n'y a aucun résultat lexical. La question et les passages sont envoyés au fournisseur. Aucun rapport ni clé n'est enregistré par ce prototype ; la sortie JSON est affichée dans le terminal. La réponse peut manquer ou être invalide si le plafond de tokens est insuffisant.

## Benchmark actuel et limites

`data/rag_dev_cases.json` contient six questions de développement avec passage attendu, conçues en même temps que le corpus. `eval` calcule Hit@k et MRR@k de recherche seulement. Un score parfait sur ces six exemples ne démontre ni généralisation ni qualité RAG, et ne mesure ni fidélité de réponse ni exactitude des citations. Les annotations sont provisoires et pas indépendantes. Les tests automatisés utilisent un modèle HTTP simulé ; aucun modèle réel n'a été évalué pour cette version.

Avant de parler de système sérieux : récupérer des documents complets dont les droits et la redistribution sont établis, garder des instantanés et métadonnées de version, gérer extraits non fiables et prompt injection, dates de validité, erreurs et contradictions ; concevoir un jeu indépendant couvrant tourisme, business, formulations multilingues, absence d'information et informations périmées ; évaluer rappel et classement par passage ainsi que l'abstention, fidélité et citations par revue humaine. Comparer ensuite lexical, dense et hybride à budget identique. Ne pas indexer automatiquement des pages tierces ni traiter des démarches administratives comme garanties actuelles.
