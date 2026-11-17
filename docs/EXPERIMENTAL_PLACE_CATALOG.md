# Catalogue de lieux expérimental

Ce prototype importe un CSV au format de la copie Hugging Face du jeu « Hôtels et restauration en Côte d'Ivoire » vers SQLite, sans GPU ni service cloud. Il est **séparé de l'agent et du benchmark** : il n'étend pas encore les outils du modèle. La recherche est structurée et lexicale, pas vectorielle ni un RAG documentaire.

Source d'origine : https://data.gouv.ci/datasets/hotels-et-restauration-en-cote-divoire (7 222 lignes annoncées, mise à jour indiquée : 23 septembre 2022). Copie consultée : https://huggingface.co/datasets/electricsheepafrica/africa-cote-d-ivoire-hotels-et-restauration-en-cote-d-ivoire-2e09f9a1 . Le portail mentionne une licence ouverte ; les données sont attribuées à OpenStreetMap : créditer © OpenStreetMap contributors, vérifier ODbL et les conditions exactes avant redistribution. https://www.openstreetmap.org/copyright

**Le CSV complet n'a pas été téléchargé ni testé dans ce prototype.** Les tests portent sur des lignes synthétiques. Les 7 222 lignes ne signifient pas 7 222 fiches utilisables : nom, catégorie ou coordonnées peuvent manquer. Le script rejette les champs obligatoires absents, les catégories hors hôtel/café/restaurant/bar, les géométries non ponctuelles et les doublons d'identifiant ; un comptage est retourné. La qualité, la couverture, les doublons d'établissements portant des identifiants différents et le statut actuel ne sont pas vérifiés.

La copie affiche la table et ses colonnes. Obtenir auprès de cette source un export CSV UTF-8 intégral avec `id`, `nom_de_l_etablissement`, `categorie`, `geometry` (GeoJSON Point), `ville_ou_commune`. Si l'export ne contient pas ces colonnes ou utilise un autre format, il faut adapter l'importeur ; il échoue explicitement. Les numéros de téléphone et autres champs ne sont volontairement pas importés.

PowerShell, à la racine du dépôt :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_place_catalog.py -v
New-Item -ItemType Directory -Force local_data
.\.venv\Scripts\python.exe experiments/place_catalog.py import-csv --csv local_data/lieux.csv --db local_data/lieux.sqlite
.\.venv\Scripts\python.exe experiments/place_catalog.py search --db local_data/lieux.sqlite --category restaurant --district Cocody --limit 10
```

La base cible ne doit pas déjà exister. Le résultat de l'import indique le nombre accepté/rejeté, l'empreinte SHA-256 du fichier source et la provenance. Les résultats sont historiquement datés et ne prouvent pas que les lieux sont ouverts ; aucune disponibilité, réservation, note ou prix actuel n'est fourni. La recherche accent-insensible est une correspondance littérale et la commune peut manquer. Garder le CSV et la base hors Git.

Suite avant intégration à l'agent : auditer le fichier réel, répartir les rejets par cause, mesurer couverture par catégorie/commune et duplications, concevoir l'identifiant et la provenance jusqu'aux citations, prévoir pagination, fraîcheur et gestion d'échec. Figer une copie séparée de la fixture d'évaluation. Pour les documents, ajouter ensuite un corpus autorisé, extraction avec provenance, recherche lexicale puis hybride et un jeu de pertinence indépendant. Ne pas confondre RAG documentaire et base structurée des lieux.
