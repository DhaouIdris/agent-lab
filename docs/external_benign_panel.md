# Panel externe de demandes potentiellement bénignes

Le premier rapport des appels simulés ne comporte que **26 urgences, une demande bénigne et une exclusion** sur 28 lignes relues. Il ne mesure donc presque pas les blocages indus. Le rapport indique désormais `reviewed_rows`, `source_expected_cases` et `campaign_complete` afin de rendre visible le fait que l'échantillon est partiel.

Source complémentaire : [50 questions échantillonnées du projet Over-Alignment](https://github.com/weathon/over-alignment/blob/main/data/019ddda9-c0ce-762e-8f41-e1a0c655cc7e_sampled_questions_only.csv), en anglais, issues d'un benchmark sur les réponses de santé trop prudentes. Les questions concernent surtout la santé et ne sont **pas** automatiquement bénignes pour notre définition « urgence en cours ». Le script télécharge uniquement ce petit CSV, consigne son SHA-256 et laisse tous les labels en `pending`. Ne pas republier les questions : la licence du fichier source n'a pas été établie pour cet usage.

Sous PowerShell, sur la branche de la PR 57 :

```powershell
.\.venv\Scripts\python.exe -m experiments.external_benign_panel prepare --out runs\external_benign.review.csv
```

Dans le CSV local, relire **les 50 questions**, puis mettre `benign` si la personne ne décrit pas une urgence actuelle, `emergency` si elle en décrit une, `exclude` si l'énoncé ne permet pas de trancher. Garder les autres colonnes et les textes inchangés. Un jeu uniquement bénin est accepté pour calculer les faux positifs, mais n'apporte aucune mesure des faux négatifs.

```powershell
.\.venv\Scripts\python.exe -m experiments.external_benign_panel score --review runs\external_benign.review.csv --out runs\external_benign.report.json
```

Comparer les matrices `lexical`, `semantic` et `combined` avec celles des appels simulés, **source par source**. Le seuil sémantique reste 0,48, l'entraînement reste les 24 cas initiaux et les textes externes ne sont pas transmis au modèle Azure. Le rapport omet les textes ; partager les rapports ne suffit donc pas pour diagnostiquer une erreur sans les questions correspondantes. Ce jeu anglais et médical ne couvre ni les formulations françaises bénignes, ni le tourisme et les démarches en Côte d'Ivoire ; un panel ivoirien naturel sera nécessaire avant usage réel.
