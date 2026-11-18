# Recherche hybride et Prompt Shields : prototypes

## Recherche hybride distante, sans poids locaux

`experiments.hybrid_retrieval` combine BM25 local et similarité cosinus d'embeddings via Reciprocal Rank Fusion (RRF). Un seul appel envoie la question et **tous** les passages à l'API Azure embeddings ; le vecteur de chaque passage est recalculé à chaque exécution. Limite expérimentale : 100 passages. Pas d'index persistant, pas de seuil de pertinence sémantique et aucun appel au modèle génératif. Le résultat hybride est une expérience de recherche séparée : il n'est pas encore branché à `document_rag ask` ou au benchmark batch.

Déployer d'abord un modèle d'embeddings compatible dans une ressource Azure et connaître son nom de déploiement (distinct de celui du modèle de chat). Les appels peuvent être facturés. Ne transmettre que des documents autorisés : le corpus complet et la question sont envoyés à Azure. L'endpoint est celui de la ressource Azure OpenAI, avec `/openai/v1`, sans clé ni paramètres d'URL. La clé est demandée masquée ou lue depuis `AGENTLAB_API_KEY` ; elle n'est pas écrite dans les résultats.

```powershell
.\.venv\Scripts\python.exe -m experiments.hybrid_retrieval --corpus data/rag_seed_extended.json --question "Où se trouve le parc de la Comoé ?" --endpoint https://MA-RESSOURCE.openai.azure.com/openai/v1 --deployment MON-DEPLOIEMENT-EMBEDDING | Out-File -Encoding utf8 hybrid_result.json
```

Remplacer l'endpoint et le déploiement par les valeurs réelles ; si besoin saisir la clé sans redirection de sortie ou définir `AGENTLAB_API_KEY` pour la session. Comparer BM25 et hybride sur des questions annotées indépendamment (y compris sans réponse), en mesurant rappel, précision, latence et coût. RRF ne garantit pas la pertinence : même un passage sémantiquement peu pertinent peut être retourné.

## Prompt Shields facultatif

Pour l'entrée `document_rag ask`, l'option `--prompt-shield-endpoint` active une vérification supplémentaire du prompt et des titres/textes retrouvés via Azure AI Content Safety `text:shieldPrompt` API 2024-09-01. Les passages sont répartis par lots de cinq et tout signal positif bloque la génération. Une erreur réseau, un filtre ou une réponse incorrecte interrompt la requête (`guard_unavailable`) : aucun modèle génératif n'est appelé. Le filtre lexical existant agit aussi. L'option n'est pas activée par défaut, ni branchée au benchmark batch ou aux autres outils de l'agent. Elle n'est pas une garantie de détection.

Une ressource Content Safety appropriée, sa clé et la disponibilité de Prompt Shields sont nécessaires ; ne pas supposer que la clé Foundry GPT suffit. La question et les passages sont envoyés à Content Safety, qui peut être un service et une ressource distincts ; vérifier les droits, coûts et conditions applicables. Le français doit être évalué ; un détecteur externe peut manquer des attaques et bloquer du contenu légitime. La protection des secrets et les autorisations d'actions doivent rester dans le code hôte, indépendamment des détecteurs.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag ask --corpus data/rag_seed_extended.json --question "Où est le parc de la Comoé ?" --prompt-shield-endpoint https://MA-RESSOURCE.cognitiveservices.azure.com
```

La clé de génération est saisie masquée ou fournie via `AGENTLAB_API_KEY`. La clé Content Safety est saisie séparément ou fournie via `AGENTLAB_SHIELD_KEY`. Aucun endpoint ni clé n'est enregistré dans le résultat. Les tests unitaires utilisent des services simulés : aucun test live Azure ni mesure de qualité du détecteur n'a été effectué. Pour évaluer sérieusement, créer un adaptateur d'évaluation séparant détections, erreurs fournisseur et faux positifs sur un jeu indépendant.
