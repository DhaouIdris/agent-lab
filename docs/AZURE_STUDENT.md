# AgentLab sur PC léger + Azure for Students

Version 0.2.0 — 16 novembre 2026. Aucun déploiement ni appel Azure effectué pour produire ce lot.

## Répartition du travail

Le PC exécute Python, les neuf outils simulés, les garde-fous, les assertions et les rapports. Seule l'inférence du modèle part vers Azure par HTTPS. Aucun téléchargement de poids, GPU, Docker, PyTorch, serveur de base vectorielle ou VM n'est nécessaire pour cette étape. Le modèle reçoit les conversations et les résultats d'outils : utiliser uniquement les données de test fournies.

La logique agentique reste dans `ci_agentlab/providers.py`. Un service d'agents managé supplémentaire n'est pas requis : le modèle choisit les appels, Python valide les arguments et permissions, exécute l'outil, puis renvoie son résultat au modèle.

## 1. Déployer depuis Foundry Toolkit ou le portail

1. Sélectionner la souscription **Azure for Students**, puis un groupe de ressources et une ressource/projet Foundry.
2. Ouvrir le catalogue et examiner l'offre exacte : fournisseur, type de déploiement, région, quota disponible et tarif.
3. Pour vérifier rapidement le branchement, `gpt-4.1-mini` est une baseline propriétaire possible si disponible dans cette souscription. Ce choix ne constitue pas un classement de modèles et ne remplace pas l'objectif de comparaison avec des modèles ouverts.
4. Pour un modèle à poids ouverts, vérifier séparément sa licence, l'offre vendue directement par Azure, l'éligibilité au crédit, la route Chat Completions, les appels d'outils et le mode JSON. La présence dans le catalogue ne garantit aucun de ces points. Ne pas choisir une offre Marketplace ou un endpoint GPU dédié en supposant qu'il consomme le crédit étudiant.
5. Choisir un déploiement à la demande **Standard**, **Global Standard** ou **Data Zone Standard**, selon disponibilité et contraintes de région. Ce lot ne prévoit pas de capacité provisionnée/PTU. Nom suggéré : `agentlab-baseline`.
6. Relever le nom du déploiement, le modèle et sa version, la région, les limites TPM/RPM et l'URL d'inférence. Conserver la clé uniquement sur ton poste.

L'offre publique annonce 100 USD de crédit sur 12 mois ; cela ne renseigne pas ton solde restant. Les conditions excluent notamment les produits Marketplace et certains produits tiers. L'accès effectif à un modèle dépend de l'offre et des quotas de ta souscription. Si le déploiement est refusé, relever le code d'erreur et le quota affiché ; ne pas changer automatiquement d'offre de facturation.

## 2. Installer localement

Extraire le ZIP. Dans le terminal PowerShell de VS Code, ouvrir le dossier `agentlab` contenant `run_azure.py`. Python 3.11 ou 3.12 est requis.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ci_agentlab validate
Copy-Item azure.example.json azure.json
```

Ces validations ne contactent aucun modèle. L'installation de Pydantic utilise le registre de paquets. L'utilisation directe de l'exécutable du venv évite de modifier la politique PowerShell pour activer l'environnement.

## 3. Configurer `azure.json`

Conserver toutes les clés du fichier d'exemple et renseigner :

| Champ | Valeur attendue |
|---|---|
| `base_url` | Base d'inférence, par exemple `https://TA-RESSOURCE.openai.azure.com/openai/v1` |
| `deployment` | Nom exact du **déploiement**, par exemple `agentlab-baseline` |
| `underlying_model`, `model_version`, `region` | Valeurs affichées dans Foundry |
| `deployment_type` | `GlobalStandard`, `DataZoneStandard` ou `Standard` selon le déploiement |
| `auth_header` | `api-key` pour ce parcours |
| `api_version` | `null` pour la route v1 utilisée ici |
| `token_parameter` | `max_completion_tokens` ; `max_tokens` seulement si le contrat du modèle l'exige |
| `input_price_per_million`, `output_price_per_million` | Tarifs réellement affichés, dans la même devise ; sinon garder les deux à `null` |
| `currency` | Devise correspondant aux deux tarifs |

L'URL du projet Foundry (`/api/projects/...`) et l'URL complète finissant par `/chat/completions` ne sont pas des valeurs valides pour `base_url`. Le lanceur ajoute lui-même `/chat/completions`. D'autres routes d'inférence nécessiteraient une adaptation explicite.

Ne pas mettre de clé dans ce JSON. Le terminal la demande en saisie masquée à chaque commande réseau, sauf si `AGENTLAB_API_KEY` existe déjà dans l'environnement. Elle n'est pas écrite dans les rapports. Ne pas la communiquer dans le chat ou dans une capture d'écran. `azure.json`, `.env` et `runs/` sont ignorés par Git.

## 4. Valider la connexion avant le benchmark

```powershell
.\.venv\Scripts\python.exe run_azure.py check
.\.venv\Scripts\python.exe run_azure.py preflight
```

`check` valide seulement la configuration locale. `preflight` effectue au maximum **deux requêtes facturables** : un appel forcé à `get_entity_details`, puis une réponse JSON qui doit refléter le résultat. Le succès exige `"passed": true`. Cela vérifie un aller-retour outil, pas la robustesse générale ni le décodage JSON Schema strict.

Le résultat est conservé dans `runs/azure_preflight.json`. Le lanceur exige un preflight réussi avec exactement la même configuration avant les campagnes. Un changement de tarif ou de région dans le fichier modifie aussi cette empreinte : relancer le preflight après modification.

## 5. Augmenter progressivement le volume

```powershell
.\.venv\Scripts\python.exe run_azure.py smoke
.\.venv\Scripts\python.exe run_azure.py pilot
.\.venv\Scripts\python.exe run_azure.py benchmark
```

Exécuter d'abord `smoke`, examiner ses résultats, puis seulement les étapes suivantes.

| Étape | Scénarios | Répétitions | Plafond de requêtes modèle |
|---|---:|---:|---:|
| `smoke` | 2 : recherche et information inconnue | 1 | 24 |
| `pilot` | 40 | 1 | 400 |
| `benchmark` | 40 | 3 | 1 200 |

Un scénario peut contenir plusieurs tours et plusieurs requêtes modèle. Les plafonds peuvent arrêter une campagne complexe avant sa fin. Un rapport incomplet n'est pas comparable à une campagne complète ; ajuster consciemment le lot ou les plafonds du lanceur, et garder les mêmes paramètres entre candidats.

Chaque campagne crée un dossier daté dans `runs/` avec `report.json`, `human_review.json`, `review_mapping.json` et les métadonnées Azure. `--dry-run` affiche la commande sans clé ni requête réseau. Un chemin `--out` existant est refusé par le lanceur pour préserver les résultats.

Les requêtes sont séquentielles, espacées d'au moins 15 secondes entre débuts par défaut, avec 1 200 tokens de sortie maximum, 6 appels modèle et 8 appels d'outils maximum par tour. Le délai par tour est de 180 secondes, avec une attente réseau d'au plus 30 secondes par appel, diminuée de l'espacement éventuel. Ces valeurs ne garantissent pas le respect du quota TPM : le prompt et l'historique comptent aussi. Un modèle à raisonnement peut consommer le plafond de sortie avant de produire un JSON utile.

Une erreur HTTP/réseau interrompt le scénario et la campagne sans nouvelle tentative automatique. Les erreurs de comportement du modèle restent des échecs à analyser. `campaign_complete: true` signifie que la campagne est terminée, pas que les scénarios sont réussis.

## 6. Lire les erreurs et contrôler le coût

| Symptôme | Vérification utile |
|---|---|
| HTTP 401/403 | Clé correspondant à la ressource, autorisations, authentification par clé autorisée |
| HTTP 404 | URL d'inférence et nom du déploiement exacts |
| HTTP 400 | Paramètres supportés : token limit, tools, tool_choice et JSON |
| HTTP 429 | Quotas RPM/TPM, capacité disponible, espacement ; attendre avant une relance consciente |
| Preflight avec mauvais outil ou mauvais JSON | Examiner la compatibilité et la sortie ; ne pas contourner le contrôle en modifiant le marqueur |
| Coût `null` | Tarifs non renseignés ou usage manquant ; cela ne veut pas dire gratuit |
| JSON final tronqué | Plafond de génération potentiellement insuffisant ; vérifier la trace et le modèle avant de l'augmenter |

La formule indicative est `(tokens_entrée × tarif_entrée + tokens_sortie × tarif_sortie) / 1 000 000`. Elle ne modélise pas les remises cache ni tous les cas de facturation. Le plafond de requêtes n'est pas une limite financière et une alerte budgétaire Azure n'est pas un arrêt instantané. Contrôler le solde et le coût dans Azure après le pilote avant de lancer trois répétitions.

## Ce que nous pourrons conclure

Le rapport permet d'étudier choix d'outil, arguments, citations structurées, gestion des inconnues, autorisations, injections, pannes, coût et latence sur ces cas. Il faut lire les réponses libres et remplir la revue humaine. Les 40 scénarios sont un jeu de développement, pas un test indépendant ni une couverture de toutes les questions.

Les annotations et les données sont limitées ; les réservations restent simulées. Une baseline à workflow fixe et un jeu de test indépendant sont encore à construire avant de conclure à un avantage agentique ou à une aptitude à la production.

## Sources officielles consultées le 16 novembre 2026

- Offre et exclusions : https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0170p/
- Foundry Toolkit : https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/get-started-projects-vs-code
- Modèles vendus par Azure : https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure
- Contrat REST v1 : https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat

La disponibilité propre à ta souscription n'a pas été vérifiée.
