# Classement de lieux autour d'une position connue

Une position transmise explicitement au programme (`--user-location LAT LON`) permet de répondre à une demande de restaurants, cafés, hôtels, bars, fast-food ou glaciers proches. La validation de la position et le filtre d'injection ont lieu avant tout appel externe. La recherche locale choisit au plus 12 fiches de la catégorie demandée à 10 km ou moins sur la carte. Cette présélection est seulement interne : le classement visible utilise les **distances d'itinéraire** fournies par la matrice openrouteservice, en marche par défaut ou en voiture si la question le précise. Une requête ORS suffit pour cette sélection. Une distance manquante ou un échec du service ne devient pas une distance à vol d'oiseau.

Le résultat contient au plus trois lieux, ou un seul si la question demande le plus proche. Il mentionne la limite de 12 candidats, le rayon local, la date 2022 des fiches et l'absence de confirmation de l'activité actuelle. Il ne garantit ni que ces lieux sont encore ouverts, ni qu'ils sont les plus proches parmi tous les établissements réels : catalogue incomplet et shortlist limitée. La position n'entre pas dans la trace, les réponses ou `report.json`. Elle est envoyée à ORS pour obtenir les trajets ; les positions des lieux y sont également envoyées.

Depuis la racine du dépôt avec `ORS_API_KEY` dans `.env` :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent --db local_data/lieux.sqlite --corpus data/rag_integrated_dev.json --user-location 5.3201 -4.0120 --question "Quels restaurants sont proches de moi ?"
~~~

La campagne de huit cas contient quatre demandes avec position connue, une position invalide, une injection mêlée à une recherche, une demande sans position et une zone sans fiche. Elle n'inclut pas de position réelle d'utilisateur ; ses coordonnées sont des valeurs de développement enregistrées dans le fichier de cas. La campagne en direct utilise la clé Azure habituelle pour l'initialisation du runner, mais les quatre demandes de proximité n'appellent pas le modèle :

~~~powershell
$run = "runs/nearby_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/natural_nearby_8.json --db local_data/lieux.sqlite --private-review --out $run
.\.venv\Scripts\python.exe -m experiments.readable_review $run
~~~

La version `data/natural_user_expansion_36_v2.json` corrige **uniquement** deux annotations du panel précédent : E-D01 pose désormais une question étayée par le passage `UNESCO_BASSAM__0003`, sans demander l'année d'inscription absente du corpus ; E-A06 est une explication conceptuelle qui n'exige pas la consultation de la fiche de PIB. Le panel original et le rapport déjà produit restent inchangés. Pour retester les cinq échecs pertinents sans lancer toute la campagne :

~~~powershell
$old = "runs/followup_old_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/natural_user_pilot_24.json --case N-C01 --case N-L01 --db local_data/lieux.sqlite --private-review --out $old
.\.venv\Scripts\python.exe -m experiments.readable_review $old

$new = "runs/followup_new_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/natural_user_expansion_36_v2.json --case E-C02 --case E-C05 --case E-A04 --case E-D01 --case E-A06 --db local_data/lieux.sqlite --private-review --out $new
.\.venv\Scripts\python.exe -m experiments.readable_review $new
~~~

Ce diagnostic est un jeu de développement, pas une estimation indépendante. Les contrôles automatiques ne valident pas le ton, la réalité de l'activité, la couverture géographique ni la pertinence de chaque phrase ; relire les passages et les réponses. Une répétition des cas G01 et G03 est possible avec `--consistency` après la première passe. Un test de matrice en direct n'a pas été exécuté dans le dépôt sans la clé ORS.
