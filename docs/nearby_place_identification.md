# Identifier les lieux dont le nom est vague ou répété

Le catalogue historique de 2022 contient de nombreuses fiches appelées simplement « Café », « Kiosque » ou « Hotel », et plusieurs lieux aux noms similaires. Pour les réponses de proximité, l'agent conserve les **mêmes lieux et le même classement par distance d'itinéraire**. Il marque « nom générique » si l'intitulé ne permet guère de reconnaître un établissement. Si deux fiches affichées ont le même nom, ou des noms similaires à moins de 75 mètres, chacune reçoit un lien vers son objet OpenStreetMap. Ces liens sont aussi fournis pour les noms génériques. Un avertissement signale que deux fiches proches ne constituent pas nécessairement deux établissements distincts.

Les liens sont construits uniquement à partir d'identifiants locaux de forme `node/123`, `way/123` ou `relation/123`, sans inclure la position de l'utilisateur ni la clé ORS. Une fiche OSM actuelle peut avoir changé depuis l'inventaire de 2022 ; le lien est un repère pour vérifier le lieu, **pas** une preuve d'ouverture, d'activité ou de catégorie actuelle. Un identifiant malformé ne devient pas un lien. Si un lieu générique ne possède pas d'identifiant OSM valide, l'agent garde son nom et précise seulement « nom générique ».

Pour relire cinq réponses réelles depuis la branche de cette PR ou après fusion, avec la base `local_data/lieux.sqlite` et `ORS_API_KEY` dans `.env` :

~~~powershell
$run = "runs/nearby_identity_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/nearby_identity_review_5.json --db local_data/lieux.sqlite --private-review --out $run
.\.venv\Scripts\python.exe -m experiments.readable_review $run
~~~

Le jeu rejoue les positions synthétiques des cas où les noms « Kiosque », « Seen Hotel », « Garbadrome », « Café » et « Hotel » ont déjà posé problème. Il nécessite au plus cinq appels de matrice ORS ; ces cinq demandes n'appellent pas Azure pour produire les réponses de proximité. `report.json` ne reproduit ni les réponses libres ni les coordonnées ; la revue privée et sa version Markdown servent à juger si les liens et l'avertissement sont utiles et naturels. Le catalogue et ses éventuels doublons ne sont pas modifiés.
