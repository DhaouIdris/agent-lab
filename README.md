# Côte d'Ivoire AgentLab — v0.2.0

**Pour essayer l'agent intégré avec son propre modèle et ses propres clés : [guide de la branche de test](docs/SHAREABLE_TEST.md).**

Un laboratoire Python pour construire et évaluer un agent à outils tourisme/business.
**Le premier lot fonctionne hors ligne et ne fait aucune réservation réelle.**

**PC léger + Azure for Students : commencer par [le guide Azure](docs/AZURE_STUDENT.md).**
Le nouveau lanceur `run_azure.py` garde les outils et les tests sur le PC et délègue l'inférence à Azure. Il propose un contrôle de protocole en deux requêtes, puis des campagnes progressives. Aucun modèle ni ressource Azure n'a été utilisé pour valider ce lot ; les tests de transport emploient des réponses simulées.

## Ce qui est livré

- Neuf outils exécutables, contrats d'entrée Pydantic stricts et JSON Schema exportés.
- Une enveloppe de réponse commune validée ; les charges métier restent des dictionnaires en v0.1.
- Un exécuteur contrôlant permissions, arguments, confirmation exacte, expiration, idempotence et budgets d'appels.
- Un agent à boucle bornée et un adaptateur HTTP Chat Completions compatible, configurable pour un endpoint local ou distant.
- Quarante scénarios de **développement**, avec conversations, règles de notation, références et replays de contrôle.
- Des tests automatisés de sécurité/fonctionnement, y compris concurrence et pannes après création.
- Un moteur de rapports, une comparaison appariée, et un fichier de revue humaine.

**Aucun modèle réel n'a été évalué dans le rapport livré.** Le passage des replays signifie que le banc de test accepte les comportements de référence. Ce n'est ni un taux de réussite d'IA, ni une démonstration de résistance d'un modèle aux injections.

## Démarrer en cinq minutes

Python 3.11 ou 3.12. Ouvrir le terminal à la racine du dossier extrait, là où se trouve ce README.

```bash
python -m venv .venv
```

Sous Windows PowerShell :

```powershell
.\.venv\Scripts\Activate.ps1
```

Sous Linux/macOS :

```bash
source .venv/bin/activate
```

Puis :

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m ci_agentlab validate
python -m ci_agentlab replay --repeat 3 --out runs/reference
```

Ces commandes de validation/replay n'appellent aucun fournisseur LLM. L'installation de la dépendance nécessite un accès au registre de paquets. `unittest` appartient à Python ; aucune installation de pytest n'est requise.

Les résultats sont écrits dans `runs/reference/report.json`. Le champ `kind` indique explicitement `oracle_replay_NOT_MODEL_PERFORMANCE`.

## Brancher un modèle

Il faut un serveur exposant `/chat/completions`, les appels d'outils et les messages de rôle `tool`. Fournir une **URL de base**, pas l'URL complète `/chat/completions`.

Commencer par deux cas, puis élargir :

```bash
python -m ci_agentlab run --base-url http://localhost:8000/v1 --model NOM_EXACT_DU_MODELE --case S01 --case U01 --max-provider-calls 20 --out runs/smoke
```

Sur Ollama, si le modèle et le serveur prennent en charge ce protocole, l'URL de base usuelle est `http://localhost:11434/v1`. La compatibilité effective doit être testée, pas déduite de la seule présence du modèle.

Campagne complète :

```bash
python -m ci_agentlab run --base-url http://localhost:8000/v1 --model NOM_EXACT_DU_MODELE --repeat 3 --max-provider-calls 1000 --out runs/model_a
```

Pour un endpoint authentifié, placer le secret dans la variable d'environnement `AGENTLAB_API_KEY`. Ne jamais l'inscrire dans les scénarios, le prompt, un fichier partagé ou une commande publiée.

L'adaptateur utilise par défaut `Authorization: Bearer ...`. Pour un endpoint qui exige `api-key`, ajouter `--auth-header api-key`. `--api-version` est disponible pour les routes qui l'exigent. Une URL Azure peut inclure le chemin du déploiement approprié ; vérifier le contrat du déploiement. **Il n'y a pas d'adaptateur Responses API, d'authentification Entra automatique, ni de validation effectuée sur une souscription Azure dans ce lot.**

Options utiles :

- `--max-output-tokens 2000` : plafond de génération par appel, sous réserve du contrat du fournisseur.
- `--token-parameter max_completion_tokens` : nom du paramètre de plafond utilisé pour Azure v1.
- `--min-interval-seconds 15` et `--turn-timeout-seconds 180` : espacement des requêtes et budget de temps par tour.
- `--stop-on-provider-error` : arrêter la campagne au premier échec HTTP/réseau enregistré.
- `--max-provider-calls 240` : plafond global de tentatives réseau de la campagne ; le modifier consciemment pour une campagne plus grande.
- `--reasoning-effort low` : uniquement si l'endpoint accepte ce paramètre.
- `--input-price ... --output-price ...` : prix par million de tokens, dans la même devise. Sans ces valeurs ou sans usage retourné, le coût est **inconnu**, jamais inventé.

Le calcul tarifaire est simple : il ne modélise pas les remises cache, les paliers, les jetons facturés non déclarés ni la facturation GPU horaire. Le plafond d'appels n'est pas un plafond financier contractuel. Les erreurs transitoires sont réessayées au maximum deux fois avec backoff et jitter dans le délai et le budget d'appels ; 400, 401, 403 et 404 ne sont pas réessayées. Un timeout peut avoir été facturé même sans usage retourné.

Si le plafond global interrompt la campagne, `campaign_complete` passe à `false` et la comparaison refuse ce rapport. Augmenter consciemment le budget ou réduire le lot, puis réexécuter les deux candidats dans les mêmes conditions.

## Lire les résultats

- `report.json` : configuration, empreintes du corpus/code, résultats par scénario, traces, erreurs, latence, usage et coûts disponibles.
- `human_review.json` : sorties et traces avec grille de revue, sans nom de modèle. À distribuer sans la configuration et la table de correspondance.
- `review_mapping.json` : correspondance conservée par le responsable de l'expérience.

`automatic_pass_rate` ne vérifie pas toute la sémantique du texte libre. `human_adjudicated_task_success_rate` reste `null` tant qu'aucune consolidation humaine n'a été effectuée. Les résultats de revue ne sont pas automatiquement importés dans cette version.

Pour comparer deux rapports de modèles sur exactement le même corpus et le même code :

```bash
python -m ci_agentlab compare runs/model_a/report.json runs/model_b/report.json --out runs/comparison.json
```

L'outil refuse de comparer un replay de référence comme s'il s'agissait d'un modèle. Il calcule une différence appariée de taux automatiques et un intervalle bootstrap par scénario. Il ne sélectionne pas automatiquement un modèle de production.

## Données et portée

Le corpus volontairement minuscule contient **deux observations historiques de lieux réels**, deux entrées d'un programme événementiel et deux annotations documentaires. Il sert au fonctionnement du banc de test ; il ne représente pas l'offre d'Abidjan.

Les lieux proviennent de deux lignes de l'API data.gouv.ci observées pendant le cadrage, issues d'OSM et datées de 2022. La nouvelle tentative de récupération lors de l'implémentation a échoué (HTTP 503). Leur activité actuelle n'est pas vérifiée.

Tous les prix d'offres, réservations, fenêtres d'ouverture ajoutées par les scénarios et durées routières sont **des paramètres synthétiques de simulation**, séparés des faits sources. Aucun hôtel ou café n'a été inventé pour remplir l'inventaire. Les cas concernant ces catégories doivent donc reconnaître la couverture manquante.

Le planificateur vérifie l'ordre de visites fourni. Il ne cherche pas un ordre optimal, ne dispose pas du trafic réel et ne garantit pas un trajet dont la durée manque. Son coût connu est un sous-total, pas un budget garanti lorsque des postes sont inconnus.

## Structure

| Chemin | Rôle |
|---|---|
| `ci_agentlab/contracts.py` | Entrées typées, réponse commune et réponse finale |
| `ci_agentlab/tools.py` | Neuf outils et contrôles de sécurité |
| `ci_agentlab/providers.py` | Adaptateur HTTP et boucle agentique |
| `ci_agentlab/evaluation.py` | Assertions, état final et agrégations |
| `data/scenarios.json` | Quarante cas et annotations attendues |
| `data/oracle_replays.json` | Plans de référence, interdits au contexte du modèle |
| `data/world.json` | Faits minimaux et provenance |
| `schemas/` | JSON Schema et définition des outils |
| `docs/SECURITY.md` | Matrice de permissions et modèle de menace |
| `docs/BENCHMARK.md` | Protocole, métriques et limites |
| `tests/test_lab.py` | Tests unitaires et de régression |
| `tests/test_azure.py` | Configuration Azure, protocole simulé et limites d'appels |
| `run_azure.py`, `azure.example.json` | Lancement progressif sans SDK ni modèle local |
| `docs/AZURE_STUDENT.md` | Installation Windows, déploiement et premier benchmark |
| `reports/` | Preuves de validation de ce lot |

## Suite recommandée

1. Exécuter les deux cas smoke sur l'endpoint choisi ; résoudre les différences de protocole sans toucher à la vérité terrain pour faire monter le score.
2. Lancer les 40 cas, examiner les traces et faire une revue indépendante des annotations et réponses.
3. Élargir les faits réels, équilibrer langues/quartiers/catégories, et constituer un jeu verrouillé distinct d'au moins 100 cas.
4. Ajouter une baseline à workflow fixe avec le même modèle et les mêmes outils pour isoler la valeur du choix autonome.

La baseline à workflow fixe et le jeu de test indépendant ne sont pas inclus dans ce premier lot. Aucun score de modèle ou avantage agentique n'est revendiqué.

## Licence

Le code original est sous licence MIT. Les données tierces conservent leurs droits propres : voir `data/NOTICE.md`. La licence du code ne change pas celle des sources.

