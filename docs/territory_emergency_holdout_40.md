# Vérification d'urgence hors jeu de développement

Panel figé avant exécution : `data/territory_emergency_holdout_40.json`, SHA-256 `28530d43bc7aedd449b387fb2d1104b54d20697fa4ec4017cdeb2c8a45c77a42`. Quarante demandes naturelles, 20 décrivant une urgence immédiate et 20 ordinaires, en français et en anglais. Ce panel a été rédigé par la même équipe que le filtre et n'est **pas** une annotation indépendante ni représentative d'utilisateurs réels.

Commande :

```powershell
.\.venv\Scripts\python.exe -m experiments.eval_territory_controls --cases data/territory_emergency_holdout_40.json --out runs\territory_emergency_holdout_40.json
```

| Résultat | Nombre |
| --- | ---: |
| Urgences interceptées (TP) | 1 / 20 |
| Urgences manquées (FN) | 19 / 20 |
| Demandes ordinaires bloquées (FP) | 1 / 20 |
| Demandes ordinaires transmises (TN) | 19 / 20 |

Le rappel observé est **5 %** et le taux de faux blocage **5 %** sur ce panel. Le cas bénin bloqué est `HB20`, une traduction scolaire de « Je ne respire plus ». Les 19 urgences manquées couvrent notamment l'étouffement, une personne inconsciente, un incendie, une intoxication, un accident, un malaise neurologique et des menaces immédiates (`HE01` à `HE20`, sauf `HE09`). Les textes complets restent dans le panel local ; les rapports de score ne contiennent que les IDs et les étiquettes.

**Décision de développement :** ne pas présenter `check_emergency_intent` comme un filtre fiable, et ne pas le considérer comme un garde-fou de production. Ne pas adapter ses expressions sur ce panel puis réutiliser ces mêmes 40 cas comme preuve d'amélioration. Faire annoter un jeu externe et multi-variantes par un second relecteur ; comparer ensuite un détecteur spécialisé, des règles et leur combinaison, avec mesure des faux négatifs et faux blocages par type de situation. Réviser le court-circuit avant tout déploiement en contexte public.

Cette vérification est locale, sans Azure, sans appel d'outil et sans modèle. Elle ne mesure ni la qualité du message d'urgence ni la sécurité de la réponse résiduelle du LLM.
