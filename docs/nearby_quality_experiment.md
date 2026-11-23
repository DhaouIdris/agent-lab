# Vérifier un classement de proximité plus lisible

L'audit du catalogue de 2022 a trouvé 1 417 noms génériques sur 5 788 fiches (dont 651 sur 1 267 cafés), mais aucune de ces fiches n'est automatiquement erronée. Un même nom proche peut désigner deux commerces, deux catégories d'un même commerce, ou des représentations redondantes. La présente expérience **ne modifie pas l'agent ni la base**.

Deux étapes sont complémentaires :

1. Préparer `pairs.private.csv` depuis les revues privées de la comparaison 12/50 et de l'audit du catalogue. Les paires affichées ensemble sont prioritaires ; les noms identiques répétés sont limités pour éviter qu'un seul groupe remplisse la sélection. L'échantillon de l'audit source est limité à ses **100 premiers exemples**, donc le CSV ne représente pas les 309 paires signalées. Le champ `manual_decision` reste vide : noter `same_place`, `separate_places` ou `unknown` **après** vérification de la source et, si utile, de l'établissement. Ne pas fusionner sur cette seule base.
2. Comparer expérimentalement le top 3 habituel à un top 3 alternatif sur les huit positions synthétiques déjà utilisées. **Le lieu le plus proche dans la sélection est toujours conservé.** Pour les deux autres, si le suivant porte un nom générique ou ressemble à un lieu déjà retenu, on peut choisir une fiche au nom distinctif à condition de ne pas dépasser le trajet de référence de plus de `min(250 m, 25 %)`. Sinon, le classement original reste en place. Les itinéraires des 12 et 50 candidats sont calculés avec **une seule requête ORS par cas**, et le nombre de noms génériques, de paires proches répétées et les mètres supplémentaires sont reportés. Aucun résultat « dupliqué » n'est supprimé du catalogue.

Après récupération de la branche de la PR, ou après sa fusion, depuis la racine du dépôt sous PowerShell :

~~~powershell
$comparison = "runs/nearby_comparison_YYYYMMDDTHHMMSS"
$quality = "runs/catalogue_quality_YYYYMMDDTHHMMSS"
$review = "runs/pairs_$(Get-Date -Format yyyyMMddTHHmmss).private.csv"
.\.venv\Scripts\python.exe -m experiments.prepare_pair_review --comparison-review "$comparison/review.private.json" --quality-review "$quality/review.private.json" --out $review

$run = "runs/nearby_quality_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.nearby_quality_experiment --db local_data/lieux.sqlite --out $run
Get-Content "$run/report.json"
Get-Content "$run/review.private.json"
~~~

Remplacer les deux dossiers `YYYYMMDDTHHMMSS` par leurs noms réels. La création du CSV ne nécessite aucun service externe ; le second programme utilise `ORS_API_KEY` depuis `.env`, mais n'appelle pas Azure. `report.json` contient des métriques et ID de cas, sans noms, identifiants de lieux ni coordonnées. Les détails des trois lieux restent dans `review.private.json` ; le CSV est privé. Les huit cas sont des exemples de développement non représentatifs : même une amélioration sur ces cas doit être confirmée avec d'autres positions et avec une revue humaine avant d'adopter la règle dans l'agent.
