# Contrôle de qualité du catalogue de lieux

Le résultat des huit comparaisons 12/50 n'a montré aucune différence de classement, mais quelques réponses contiennent des intitulés génériques (« Café », « Kiosque », « Hotel »). La paire « Seen hôtel Abidjan » et « Seen Hotel Abidjan Plateau » pourrait correspondre à deux représentations d'un même établissement dans l'inventaire OpenStreetMap historique. Ces indices ne suffisent pas pour supprimer ou fusionner une fiche.

Ce diagnostic lit toute la base SQLite **sans modifier les lieux**, sans ORS ni Azure. Il compte, par catégorie, les fiches sans district, les noms entièrement génériques et les coordonnées invalides. Il compare les fiches à moins de 75 mètres, sépare les paires aux noms similaires et informatifs des paires dont les noms sont seulement génériques, et relève les noms différents au même emplacement. Il peut aussi indiquer quels résultats du top 3 d'une campagne 12/50 sont concernés. Les distances entre fiches ne servent qu'à signaler les paires à examiner : elles ne sont pas présentées à l'utilisateur comme des distances d'itinéraire.

Sur Windows, depuis la racine du dépôt, remplacer le chemin de `$comparison` par le dossier de la campagne déjà exécutée :

~~~powershell
$comparison = "runs/nearby_comparison_YYYYMMDDTHHMMSS"
$audit = "runs/catalogue_quality_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_place_quality --db local_data/lieux.sqlite --review "$comparison/review.private.json" --out $audit
Get-Content "$audit/report.json"
Get-Content "$audit/review.private.json"
~~~

Si le dossier de comparaison est indisponible, retirer `--review ...` : l'audit global fonctionne seul. `report.json` contient uniquement des décomptes et les ID des cas de développement ; `review.private.json` fournit au plus 100 exemples dans chaque groupe pour vérification des noms, IDs et catégories. Les comptages couvrent toutes les fiches, même si le fichier privé limite le nombre d'exemples. Les paires restent des *candidats* : des commerces distincts peuvent partager une enseigne, un nom générique ou un bâtiment.

Après vérification manuelle des paires, comparer l'effet de toute règle de filtrage sur la diversité et la pertinence des résultats avant de l'appliquer aux réponses. Les fiches datent de 2022 et ne démontrent pas l'activité actuelle des établissements.
