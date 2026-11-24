# Pilote d'adresse comme point de départ

La recherche d'un restaurant proche d'un lieu nommé a déjà été exercée avec le catalogue local et openrouteservice. Ce pilote vérifie l'autre chemin : une adresse absente du catalogue est envoyée au géocodeur Pelias, puis les lieux proches sont classés par temps et distance d'itinéraire. Cette requête ne passe pas par le modèle Azure.

Depuis la racine du dépôt, avec `local_data/lieux.sqlite` et `ORS_API_KEY` dans `.env`, lancer dans PowerShell :

```powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent --db local_data/lieux.sqlite --corpus data/rag_integrated_dev.json --question "Je suis à II Plateaux 7e Tranche, angle rues L129 et L84, Abidjan, quel café est le plus proche à pied ?"
```

Cette adresse est celle publiée pour le bureau de l'UNESCO à Abidjan. L'exemple vérifie la conservation des virgules et de l'intersection des rues dans la requête. Le géocodeur peut ne pas posséder cette adresse ; il ne faut pas accepter une adresse voisine comme preuve d'une résolution correcte. Vérifier le nom résolu dans `output.answer`, `trace[0].result.source`, et la distance et la durée dans `trace[1].result.ranked`. Ne pas interpréter quelques mètres comme une proximité crédible sans vérifier les points sur la carte.

Si `guard_status` vaut `origin_not_found`, `diagnostic_code` distingue `no_results` et `no_confident_match`. Dans le second cas, `geocoding_diagnostics` donne les nombres de candidats rejetés par pays, couche, confiance, numéro de rue ou format, ainsi que les couches et types de correspondance. Il ne contient ni nom ni coordonnées. Une correspondance `fallback` ou une couche `street` ne justifie pas d'utiliser un point comme adresse exacte. Un résultat `geocoding_unavailable` indique une panne ou une configuration (`missing_key`, `rate_limited`, `authentication_or_quota`, `transport`, `service_error` ou `response_format`) : ce n'est pas une adresse déclarée inexistante. Si la résolution réussit mais le classement échoue, consulter `trace[1].result.status` et vérifier la clé ORS et son quota. Ne pas partager les sorties brutes si l'adresse de départ est privée.

Ce seul essai n'établit ni la couverture nationale du géocodage ni la justesse des trajets. Tester ensuite plusieurs adresses publiques et les valider humainement sur une carte avant d'étendre cette fonctionnalité.
