# Départ par nom de lieu ou adresse

L’utilisateur peut demander « Je suis à l’hôtel Sofitel, quel est le restaurant le plus proche ? » sans fournir de coordonnées. L’agent repère le départ dans la question, cherche d’abord un nom unique dans le catalogue local, puis compare des distances et durées **d’itinéraire à pied** pour les restaurants proches avec ORS Matrix. « En voiture » sélectionne le mode voiture. Le résultat cite le restaurant, son lien cartographique, la distance et la durée estimées ; les coordonnées restent internes.

Si plusieurs lieux correspondent au départ, l’agent demande lequel est voulu **avant** d’appeler ORS. Si le catalogue ne contient pas le lieu ou si l’utilisateur donne une adresse, il tente une recherche Pelias limitée à la Côte d’Ivoire avec la clé `ORS_API_KEY` chargée de `.env`. Un résultat absent, incertain ou ambigu conduit à demander une précision. La recherche est limitée à cinq propositions ; la réponse ne considère jamais automatiquement la première comme correcte. Aucun appel Azure n’est nécessaire pour ce chemin précis.

La sélection des restaurants reste bornée aux fiches du catalogue dans un rayon cartographique de 10 km et aux 12 premières candidates avant calcul Matrix. Le classement final repose sur le trajet. Le premier lieu nommé « Restaurant » peut être peu utile malgré une distance correcte : la qualité de la recommandation nécessite une revue humaine. Le service d’itinéraire peut être indisponible ou refuser une clé ; dans ce cas la réponse ne donne pas de distance estimée à vol d’oiseau.

Test sur un catalogue réel, sans mettre de clé dans la commande :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent --db local_data/lieux.sqlite --corpus data/rag_integrated_dev.json --question "Je suis à l'hôtel Sofitel, quel est le restaurant le plus proche ?"
~~~

Comparer aussi des noms présents plusieurs fois, une adresse de rue et un lieu inconnu. Conserver les résultats privés localement pour relire les correspondances proposées par le géocodeur avant de tirer des conclusions. Ce chemin n’est pas encore une recherche générale d’itinéraires entre deux adresses.

Pour mesurer si le préfiltre de 12 candidats écarte des restaurants plus proches par trajet, utiliser le panel distinct de quatre questions naturelles. Une seule matrice ORS évalue les 50 mêmes candidats ; le script compare le classement des 12 premiers à celui des 50 et enregistre les noms dans la revue privée. Le rapport public n’affiche aucune coordonnée ni clé. Ces cas de développement ne sont pas un échantillon représentatif.

~~~powershell
$run = "runs/named_origin_compare_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.compare_named_origin_shortlists --cases data/named_origin_shortlist_4.json --db local_data/lieux.sqlite --out $run
Get-Content "$run/report.json"
~~~

Lire également `review.private.json` pour vérifier si les lieux nouvellement trouvés à 50 candidats sont plausibles et distincts. Un classement identique entre 12 et 50 n’établit pas que l’on a examiné tous les restaurants du pays ou tous ceux dans le rayon.
