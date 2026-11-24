# Pilote d'adresse comme point de départ

La recherche d'un restaurant proche d'un lieu nommé a déjà été exercée avec le catalogue local et openrouteservice. Ce pilote vérifie l'autre chemin : une adresse absente du catalogue est envoyée au géocodeur Pelias, puis les lieux proches sont classés par temps et distance d'itinéraire. Cette requête ne passe pas par le modèle Azure.

Depuis la racine du dépôt, avec `local_data/lieux.sqlite` et `ORS_API_KEY` dans `.env`, lancer dans PowerShell :

```powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent --db local_data/lieux.sqlite --corpus data/rag_integrated_dev.json --question "Je suis à II Plateaux 7e Tranche, angle rues L129 et L84, Abidjan, quel café est le plus proche à pied ?"
```

Cette adresse est celle publiée pour le bureau de l'UNESCO à Abidjan. Lors du premier essai réel, Pelias n'a renvoyé que deux correspondances de repli, dont une de type `locality`. Le refus de calculer un itinéraire est donc attendu : aucune ne localise le bureau. Ce cas sert désormais de contrôle négatif pour la conservation des virgules et de l'intersection de rues.

Une deuxième adresse publique, publiée pour un siège de société dans un [avis public](https://media-files.abidjan.net/document/docs/document_ax9kn5r1ctf.pdf), a été testée :

```powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent --db local_data/lieux.sqlite --corpus data/rag_integrated_dev.json --question "Je suis au 1 Rue des Carrossiers, Zone 3C, Abidjan, quel restaurant est le plus proche à pied ?"
```

Pelias a encore renvoyé deux correspondances `fallback` (une `locality`, une couche non répertoriée dans le diagnostic), rejetées avant le calcul d'itinéraire. Les deux adresses publiques testées échouent ; cela ne mesure pas la couverture générale du service en Côte d'Ivoire. Ne pas assouplir le filtre pour accepter une localité à la place du point de départ. La réponse utilisateur propose désormais un lieu connu à proximité, que le catalogue peut identifier.

Si `guard_status` vaut `origin_not_found`, `diagnostic_code` distingue `no_results` et `no_confident_match`. Dans le second cas, `geocoding_diagnostics` donne les nombres de candidats rejetés par pays, couche, correspondance non exacte, confiance, numéro de rue ou format, ainsi que les couches et types de correspondance. Il ne contient ni nom ni coordonnées. Une correspondance `fallback` ou une couche `street` ne justifie pas d'utiliser un point comme adresse exacte, même avec un score élevé. Un résultat `geocoding_unavailable` indique une panne ou une configuration (`missing_key`, `rate_limited`, `authentication_or_quota`, `transport`, `service_error` ou `response_format`) : ce n'est pas une adresse déclarée inexistante. Si la résolution réussit mais le classement échoue, consulter `trace[1].result.status` et vérifier la clé ORS et son quota. Ne pas partager les sorties brutes si l'adresse de départ est privée.

Avant d'annoncer la prise en charge des adresses libres, constituer un jeu indépendant d'adresses publiques vérifiées sur une carte et mesurer le taux de résolution exacte, les fausses localisations et la qualité des trajets. Une interface de choix de point sur une carte pourrait fournir une position sans afficher de coordonnées à l'utilisateur ; elle n'existe pas encore dans ce prototype.
