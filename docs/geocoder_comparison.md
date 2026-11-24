# Comparaison ponctuelle des géocodeurs

Ce benchmark **n'ajoute aucun géocodeur à l'agent**. Il compare, hors agent et sans Azure, les trois premiers résultats de Pelias (clé ORS déjà configurée), Nominatim public et Photon public pour huit hôtels d'Abidjan. Pour chacun, la page de l'exploitant publie une adresse et une position GPS. La question est envoyée sous deux formes : adresse seule et nom du lieu suivi de l'adresse. Les seize requêtes par fournisseur sont exécutées une fois, en série. Le rapport n'affirme pas qu'un hôtel voisin, même proche, soit le bon lieu.

Le jeu `data/geocoding_reference_8.json` provient des huit pages de l'exploitant indiquées dans chaque entrée. Il est concentré à Abidjan et sur un seul groupe hôtelier : il ne mesure pas la couverture de la Côte d'Ivoire ni les logements ou domiciles. Les deux adresses publiques précédemment testées (bureau UNESCO et Rue des Carrossiers) ont échoué sur Pelias, mais ne disposent pas ici d'un point GPS indépendant assez précis pour entrer dans les métriques de distance.

Depuis la branche de comparaison, dans PowerShell à la racine du dépôt :

```powershell
.\.venv\Scripts\python.exe -m experiments.geocoder_comparison --out runs/geocoder_pilot
.\.venv\Scripts\python.exe -m experiments.geocoder_comparison --out runs/geocoder_pilot --live
```

La première commande valide le jeu et affiche 48 requêtes planifiées sans appeler les services. La deuxième effectue les appels : `ORS_API_KEY` est lue dans `.env` pour Pelias, jamais imprimée. En cas d'interruption, relancer exactement la même commande et le même dossier ; les réponses déjà enregistrées sont réutilisées. Choisir un nouveau dossier si le jeu ou la sélection des fournisseurs change. Un appel échoué est lui aussi enregistré et n'est pas relancé automatiquement.

Lire d'abord `runs/geocoder_pilot/report.json` : pour chaque fournisseur et forme de question, nombre de résultats, nombre de premières réponses dans 100 et 250 mètres du point publié, réponses à plus de 1 km et erreurs de service. Le dénominateur est le nombre de cas exécutés, pas seulement les cas auxquels le fournisseur a répondu. La médiane ne porte que sur les premières réponses obtenues. `runs/geocoder_pilot/review.private.json` contient les adresses, noms et positions candidats pour vérifier sur une carte les erreurs, les homonymes et les entrées de bâtiment. Ce dernier fichier est local et ignoré par Git ; le vérifier avant de le partager. Les erreurs de localisation et l'identité du lieu nécessitent une revue humaine, même en dessous de 100 mètres. Les résultats bruts ne changent pas les garde-fous de l'agent.

Pour copier seulement le résumé plutôt que les 48 lignes du rapport :

```powershell
(Get-Content runs/geocoder_pilot/report.json -Raw | ConvertFrom-Json).summary | ConvertTo-Json -Depth 5
```

Cette expérimentation suit les [règles du Nominatim public](https://operations.osmfoundation.org/policies/nominatim/) : requêtes ponctuelles, un seul processus, au plus une requête par seconde, identification de l'application, résultats conservés localement, attribution OSM/ODbL, aucun autocomplete ni adresse privée. Le service public est inadapté comme dépendance de production sans décision explicite et contrôle du trafic. Le [serveur Photon de Komoot](https://github.com/komoot/photon#demo-server) est une démonstration sans garantie de disponibilité. L'usage de la clé Pelias/ORS reste côté serveur. Les trois services reposent largement sur des données OpenStreetMap : leurs erreurs peuvent être corrélées et un écart entre eux ne prouve pas que l'un est juste.

La suite dépend des résultats : choisir un géocodeur uniquement si les erreurs graves restent acceptables et si les conditions d'exploitation conviennent. Sinon, garder les origines par lieux nommés et prévoir un point choisi sur une carte, sans afficher la latitude et la longitude à l'utilisateur.
