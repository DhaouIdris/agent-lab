# Tester l'agent avec son propre modèle

Cette branche contient le banc historique `ci_agentlab`, l'agent intégré `experiments.unified_agent`, les gardes en amont, le corpus documentaire, le catalogue importable et les expériences. Elle ne contient ni clé, ni CSV téléchargé, ni SQLite locale, ni poids de modèle. Python 3.11 ou 3.12 suffit pour le code de l'agent ; les poids sont hébergés par le fournisseur choisi.

## Démarrage sous Windows PowerShell

```powershell
git clone --branch test/shareable-agent https://github.com/DhaouIdris/agent-lab.git
cd agent-lab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item model.example.json model.json
Copy-Item .env.example .env
```

Éditer `model.json` : `base_url` est la racine de l'API Chat Completions, **sans** `/chat/completions` ; `deployment` est l'identifiant exact du modèle fourni par **son propre service**. Azure n'est pas nécessaire. Pour une API distante compatible OpenAI, garder `auth_header: bearer` et ajuster `token_parameter` (`max_tokens` ou `max_completion_tokens`) selon le modèle. Pour un serveur local : URL `http://localhost:<port>/v1`, `AGENTLAB_API_KEY` vide. Un serveur local exige des ressources matérielles suffisantes ; sur un PC léger, utiliser une API distante. Les appels d'outils, les messages `tool` et le JSON de sortie doivent être compatibles ; le format d'API seul ne suffit pas.

Mettre **sa propre** clé du modèle dans `.env` sous `AGENTLAB_API_KEY` (ou laisser vide et saisir la clé lorsqu'elle est demandée). Si Azure et OpenAI dans le même dépôt, mettre `"api_key_env": "OPENAI_API_KEY"` dans le `model.json` OpenAI et définis `OPENAI_API_KEY` dans `.env`. Une variable PowerShell existante garde la priorité sur `.env` ; utilise un nom distinct pour ne jamais envoyer la clé Azure à OpenAI. Pour le calcul d'itinéraire et la recherche d'adresse via openrouteservice, ajouter **sa propre** clé `ORS_API_KEY` ; sans elle, ces fonctions renvoient indisponible. Le serveur LLM et openrouteservice reçoivent les requêtes correspondantes. `.env`, `model.json`, `local_data/` et `runs/` sont ignorés par Git. Ne jamais publier ces fichiers, ni partager les rapports de revue privée bruts.



## Catalogue local

Le CSV public n'est pas redistribué dans Git. Télécharger et convertir le Parquet selon [le guide du catalogue](EXPERIMENTAL_PLACE_CATALOG.md), ou fournir un CSV déjà obtenu avec les colonnes attendues. En partant du fichier `local_data/lieux.csv` :

```powershell
New-Item -ItemType Directory -Force local_data
.\.venv\Scripts\python.exe -m experiments.place_catalog audit-csv --csv local_data/lieux.csv
.\.venv\Scripts\python.exe -m experiments.place_catalog import-csv --csv local_data/lieux.csv --db local_data/lieux.sqlite
```

L'import échoue si `lieux.sqlite` existe déjà ; conserver la base existante ou utiliser un nouveau nom. La recherche de lieux repose sur cet inventaire historique ; les adresses postales, horaires et prix actuels ne sont pas fournis par le CSV. Le corpus `data/rag_integrated_dev.json` est inclus dans Git.

## Vérifier et essayer

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m ci_agentlab validate
.\.venv\Scripts\python.exe -c "from experiments.model_config import load_model_config; load_model_config('model.json'); print('Configuration valide')"
.\.venv\Scripts\python.exe -m experiments.unified_agent --config model.json --db local_data/lieux.sqlite --corpus data/rag_integrated_dev.json --question "Que dit l'UNESCO sur la forêt de Taï ?"
.\.venv\Scripts\python.exe -m experiments.chat_cli --config model.json --db local_data/lieux.sqlite
.\.venv\Scripts\python.exe -m experiments.unified_agent_batch --config model.json --db local_data/lieux.sqlite --case UA02 --private-review
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --config model.json --db local_data/lieux.sqlite --case CATALOGUE-01 --private-review
```

Les trois premières commandes n'appellent aucun LLM. Les suivantes utilisent le fournisseur choisi et peuvent être facturées. Le chat terminal accepte plusieurs questions ; `/reset` efface son contexte, `/quit` le ferme. Il conserve quatre échanges au plus, sans sauvegarde entre lancements ; chaque réponse doit établir ses propres preuves avec les outils. Vérifier les identifiants du panel choisi dans `data/audit_campaign_60.json` avant de lancer `--case`; sans `--case`, la campagne complète envoie davantage de requêtes. Le rapport va dans `runs/` : lire `report.json` puis, pour l'examen humain, `review.private.json` avec `python -m experiments.readable_review <chemin-vers-review.private.json>`. Élargir ensuite les cas ou les campagnes documentées dans `docs/`. Les scores automatiques ne jugent pas seuls la qualité des réponses. Aucun test n'effectue une réservation ou un paiement.

Le lanceur historique `run_azure.py` et son `check/preflight` restent réservés à Azure ; **les commandes de l'agent intégré n'importent pas ce lanceur** et acceptent les autres API compatibles. Les clés et quotas ne sont jamais inclus dans cette branche.


## Pour lancer le chatbot sur OpenAI ou sur Azure

```powershell
.\.venv\Scripts\python.exe -m experiments.chat_cli --config model.json --db local_data/lieux.sqlite

.\.venv\Scripts\python.exe -m experiments.chat_cli --config azure.json --db local_data/lieux.sqlite
```
Une erreur peut survenir si le paramètre max_output_token du model.json est trop faible. Il faudra le réaugmenter pour vérifier que cela fonctionne bien. L'API openrouteservice permet de trouver les adresses proches d'un lieu mais ne propose pas d'itinéraires. Plusieurs outils ne sont pas actifs car non reliés aux API nécessaires (paiement, réservation, itinéraire, etc.)
