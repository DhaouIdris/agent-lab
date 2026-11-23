# Comparaison des présélections de lieux

Les réponses d'itinéraire affichent désormais les distances inférieures à 1 km en mètres, et celles d'au moins 1 km en kilomètres. Cela concerne la recherche de lieux proches et le calcul d'un trajet entre deux coordonnées.

Le jeu `data/nearby_shortlist_comparison_8.json` contient huit positions de développement décalées des positions utilisées lors du premier essai, réparties entre restaurants, cafés, hôtels, glaciers et restauration rapide, à pied et en voiture. Ce sont des positions synthétiques, jamais celles d'un utilisateur. La campagne est indépendante d'Azure et du modèle ; elle nécessite la base SQLite locale des lieux et une clé `ORS_API_KEY` accessible via `.env`.

Depuis la racine du dépôt, dans PowerShell :

~~~powershell
$run = "runs/nearby_comparison_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.compare_nearby_shortlists --db local_data/lieux.sqlite --out $run
Get-Content "$run/report.json"
Get-Content "$run/review.private.json"
~~~

Pour chaque position, une seule requête ORS calcule les distances vers les 50 premières fiches sélectionnées à vol d'oiseau dans un rayon de 10 km. Le script compare ensuite les trois meilleurs itinéraires parmi les 12 premières et parmi les 50 premières fiches, à partir **des mêmes mesures ORS**. `wide_top3_missing_from_short` compte les résultats de la sélection large absents du top 3 actuel ; `nearest_regret_m` mesure l'écart en mètres entre les premiers résultats des deux sélections. Un classement sur 50 candidats ne garantit toujours pas le meilleur lieu du catalogue entier.

`report.json` contient les métriques agrégées sans nom, identifiant de lieu, coordonnées ni clé. `review.private.json` contient les noms, identifiants et distances des trois premiers lieux, ainsi que les paires de fiches proches de nom et de position à examiner. Une paire signalée n'est **pas** automatiquement fusionnée : des noms semblables peuvent correspondre à plusieurs établissements. Les réponses ORS manquantes et les erreurs de service sont conservées comme diagnostics, sans remplacer les distances par des vols d'oiseau. La campagne cesse après une indisponibilité ORS et conserve les cas déjà terminés.
