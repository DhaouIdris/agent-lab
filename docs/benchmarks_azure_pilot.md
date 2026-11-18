# Pilotes Azure : recherche hybride et Prompt Shields

Sur la branche `experiment/rag-injection-guard`, ces commandes expérimentales effectuent des appels Azure payants potentiels, sans télécharger de modèle localement. Ne pas envoyer de données sensibles sans autorisation : le premier pilote transmet l'ensemble des questions et passages ; le second transmet les textes de test synthétiques à Azure Content Safety. Les métriques évaluent séparément la recherche et le détecteur : pas de génération de réponse ni d'évaluation de l'agent complet. Les deux jeux ont été créés pour le projet par le même auteur et ne sont pas indépendants.

## Comparer BM25 et hybride

Déployer un modèle d'embeddings Azure et utiliser le nom de son déploiement. L'endpoint doit terminer par `/openai/v1`. La clé de la ressource est saisie de manière masquée ou lue depuis `AGENTLAB_API_KEY`. Le pilote par défaut utilise 10 passages et 12 questions : **un seul appel embeddings**, sans retry, avec tous ces textes. Un appel limité ne constitue pas une limite financière. La latence couvre l'appel, dont l'indexation des passages ; le prix et le nombre de tokens ne sont pas rapportés par cet outil.

```powershell
.\.venv\Scripts\python.exe -m experiments.benchmark_hybrid --endpoint https://MA-RESSOURCE.openai.azure.com/openai/v1 --deployment MON-DEPLOIEMENT-EMBEDDING --out hybrid_benchmark.json
```

La métrique hit et rappel porte uniquement sur les questions avec identifiants de passages pertinents. Pour les questions sans réponse, le rapport compte les requêtes renvoyant au moins un passage ; cela ne prouve pas que ces passages sont tous non pertinents, ni que l'agent répondrait incorrectement. Le RRF actuel peut toujours retourner des passages sans seuil de pertinence. En cas d'erreur API, le rapport contient une erreur générique, sans endpoint, clé, ni chemins locaux ; le détail est volontairement masqué. Ne pas partager des documents confidentiels si un corpus personnalisé est utilisé.

## Comparer Prompt Shields au filtre lexical

Déployer/configurer une ressource Azure AI Content Safety disposant de Prompt Shields ; la clé peut différer de la ressource d'embeddings ou chat. Saisir sa clé masquée ou utiliser `AGENTLAB_SHIELD_KEY`. Le pilote évalue par défaut 10 textes équilibrés, groupés par cinq : **deux requêtes maximum**, sans retry. Ce petit échantillon est un diagnostic ; il ne représente pas tout le jeu de 24 et ne suffit pas à établir la robustesse. Le rapport distingue les erreurs fournisseur (`null`) des détections. Les latences concernent un lot, pas une mesure par exemple ; coûts et usage ne sont pas fournis.

```powershell
.\.venv\Scripts\python.exe -m experiments.benchmark_prompt_shield --endpoint https://MA-RESSOURCE.cognitiveservices.azure.com --out shield_benchmark.json
```

Pour évaluer le jeu de 24 exemples en entier, remplacer la commande par la même en ajoutant `--max-requests 5` (au plus cinq requêtes) ; la disponibilité, les quotas et les tarifs dépendent de la ressource. La commande s'arrête après une erreur fournisseur et préserve un rapport partiel. Les rapports ne contiennent ni clé ni endpoint, ni textes de test ni chemin local. Une détection n'établit pas une protection complète ; la question fixe est aussi analysée et signalée séparément. Les tests automatisés simulent les services ; aucun essai Azure réel n'a encore été réalisé par l'auteur du code.
