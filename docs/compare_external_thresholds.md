# Comparer les seuils sur les deux CSV externes

Les deux jeux ont des distributions différentes : les appels simulés contiennent surtout des situations urgentes, tandis que le second réunit surtout des inquiétudes médicales en anglais. Le mélange permet de voir les faux négatifs et les faux positifs dans **une même matrice**, mais sa proportion de classes ne représente pas celle des demandes réelles en Côte d'Ivoire. Les résultats par source restent dans le JSON.

Sur la branche `fix/emergency-smoke-collision`, depuis la racine du dépôt sous PowerShell :

```powershell
.\.venv\Scripts\python.exe -m experiments.compare_external_thresholds `
  --calls runs\external_calls.review.csv `
  --benign runs\external_benign.proposed.csv `
  --merged-csv runs\external_merged.review.csv `
  --out runs\external_thresholds.report.json
```

Si tu as corrigé un ancien fichier `runs\external_benign.review.csv`, indique ce chemin à `--benign`. Le CSV fusionné est local, contient les textes et les labels, conserve l'origine et ne sera pas écrasé. Le JSON contient les métriques et les ID d'erreurs, sans les textes. Le programme entraîne **une fois** le même classifieur sur les 24 exemples de développement, puis compare les seuils 0,40 ; 0,45 ; 0,48 ; 0,50 ; 0,52 ; 0,55 ; 0,60 ; 0,65. Le filtre lexical est ajouté par union à chaque seuil. Le terminal affiche TP/FN/FP/TN et le JSON fournit les erreurs par ID et les résultats par source. Pour une sélection plus resserrée, passer par exemple `--thresholds 0.48 0.50 0.52 0.55 0.60`.

Le rapport indique `labels_reviewed: false` par défaut. **Après** avoir lu et corrigé les deux CSV d'entrée, utiliser `--labels-reviewed` pour attester cette étape ; produire un nouveau chemin `--merged-csv` car la commande refuse d'écraser une ancienne fusion. Les cas `exclude` sont conservés dans la fusion mais absents des métriques. `campaign_complete` signale si les CSV comportent les 77 et 50 lignes attendues. Ne pas choisir définitivement un seuil à partir de ces résultats : le seuil 0,48 et les règles lexicales ont déjà été influencés par des cas de ce panel. Il faudra figer ensuite un seuil et le vérifier sur un nouveau jeu indépendant.
