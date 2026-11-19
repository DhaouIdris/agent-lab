# Assistant de catalogue expérimental

Ce programme est un essai séparé : il appelle le modèle Azure configuré dans `azure.json` et lui donne un unique outil de recherche sur la base SQLite locale. Aucune fonction de réservation, aucun accès web ni moteur RAG n'est fourni. Ce n'est pas le runner du benchmark de 40 cas : son comportement n'est pas encore évalué sur un jeu indépendant.

Il faut une base créée à partir du CSV par `experiments/place_catalog.py` et un déploiement compatible Chat Completions avec appels d'outils. L'URL et la clé ne sont pas écrites par ce script ; la question et les résultats des outils sont envoyés au fournisseur du modèle. Ne pas utiliser de données sensibles pour l'essai.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_catalogue_chat.py -v
.\.venv\Scripts\python.exe -m experiments.catalogue_chat --db local_data/lieux.sqlite --question "Propose des glaciers de notre inventaire."
```

La clé est demandée en saisie masquée si `AGENTLAB_API_KEY` n'est pas définie. Au plus 4 tours de modèle, 8 tentatives HTTP (retries compris), 10 résultats par recherche et une requête d'outil par tour. Chaque appel est potentiellement facturé. Aucun score, coût ou trace n'est enregistré par ce prototype.

L'outil effectue des filtres structurés et des sous-chaînes littérales sur les noms ou communes ; il n'effectue ni recherche de proximité ni géocodage. La majorité des communes de la source sont manquantes ; un filtre par commune peut renvoyer un ensemble incomplet ou vide même si des établissements existent. Les données sont historiques et leur activité actuelle n'est pas vérifiée. Le prompt demande au modèle d'exprimer ces limites, mais le texte libre n'est pas validé contre les preuves : vérifier manuellement les réponses. Des données externes peuvent contenir des instructions adverses ; cet essai ne démontre pas la résistance aux injections.

Les tests du module utilisent un modèle simulé et un petit CSV synthétique, pas Azure ni le vrai catalogue. Avant toute utilisation produit : journaliser les preuves de façon respectueuse de la vie privée, valider les citations et sorties, ajouter un jeu de questions annoté indépendant, tests d'injection, géocodage vérifié et disponibilité des sources. Conserver le benchmark figé à part.
