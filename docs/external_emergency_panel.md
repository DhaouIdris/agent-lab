# Panel externe : appels d'urgence simulés

Source : [Multilingual Emergency Calls](https://huggingface.co/datasets/SoumiaDermouche/multilingual-emergency-calls), 77 appels simulés, Licence Ouverte 2.0. Le script extrait **le premier tour de l'appelant traduit en français**, sans le texte de l'opérateur. Ce sont des simulations situées en France, pas des questions adressées à notre agent ivoirien. Le téléchargement porte sur les données du jeu, pas sur des poids de modèle.

Sous PowerShell, depuis la racine du dépôt sur la branche du pilote :

```powershell
.\.venv\Scripts\python.exe -m pip install scikit-learn datasets huggingface_hub
.\.venv\Scripts\python.exe -m experiments.external_emergency_panel prepare --out runs\external_calls.review.csv
```

Ouvrir le CSV dans un tableur et remplir **toutes** les cellules `label` : `emergency` pour une urgence actuelle qui doit être bloquée avant l'agent, `benign` pour une demande sans urgence actuelle, `exclude` si la traduction ou le premier tour ne permettent pas de décider. Examiner aussi les textes extraits, car un appel au service d'urgence n'est pas forcément une urgence. Conserver les colonnes `id`, `source`, `revision`, `language`, `question`, `label`. La commande refuse les étiquettes `pending` et les ID en double.

```powershell
.\.venv\Scripts\python.exe -m experiments.external_emergency_panel score --review runs\external_calls.review.csv --out runs\external_calls.report.json
```

Le résultat ne contient que les identifiants, décisions et métriques, sans réimprimer les messages. Le SHA-256 du CSV relu, la révision source et le seuil 0,48 sont consignés. Le classifieur est réentraîné exclusivement sur les 24 exemples initiaux ; le panel externe n'est pas employé pour entraîner ou ajuster le seuil. Les traductions et les étiquettes humaines rendent ce test complémentaire, mais il ne mesure ni l'anglais brut ni les performances en situation réelle. Pour une comparaison solide, ajouter séparément un jeu de demandes bénignes naturelles hors contexte d'appels d'urgence.
