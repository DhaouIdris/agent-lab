# Suivi des réponses du panel naturel

La campagne de 52 questions reste figée : ses 52 réussites automatiques et ses réponses initiales ne sont pas modifiées. La revue privée du 24 novembre a trouvé qu'une demande au singulier (« le plus près ») renvoyait trois hôtels. Le correctif du routage et sa régression locale font partie de la PR 47. Ce nouveau fichier de cinq questions sert au suivi, avec un hash et des résultats distincts du panel original.

`data/holdout_response_followup_5.json` contient deux demandes de proximité au singulier (une reprise explicite du cas initial, une autre formulation), une recommandation d'un seul café, une question documentaire sur le fleuve Comoé et une demande de paiement impossible. Le nouvel indicateur `max_place_ids` compare le nombre d'identifiants de lieux retournés à la limite attendue. Il détecterait les trois hôtels du cas initial. Il ne prouve pas à lui seul que la prose ne mentionne aucun autre établissement, ni que le lieu est réellement le plus proche. Pour la question documentaire, un identifiant de passage correct ne suffit pas à justifier tous les détails de l'explication ; relire les affirmations une par une. Pour le paiement, la limite de longueur repère une réponse disproportionnée, mais ne prouve pas sa pertinence.

Après fusion de cette PR, lancer hors ligne depuis la racine du dépôt, avec le catalogue local :

```powershell
$offline = "runs/response_followup_offline_$(Get-Date -Format yyyyMMddTHHmmssfff)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/holdout_response_followup_5.json --db local_data/lieux.sqlite --out $offline
```

Le mode hors ligne n'évalue ni Azure ni ORS : les cas nécessitant ces services attendront leur appel. Un passage direct des cinq cas, puis le Markdown de revue privée :

```powershell
$run = "runs/response_followup_$(Get-Date -Format yyyyMMddTHHmmssfff)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/holdout_response_followup_5.json --db local_data/lieux.sqlite --private-review --out $run
.\.venv\Scripts\python.exe -m experiments.readable_review $run
```

Quatre cas sont marqués pour trois répétitions en sessions indépendantes. Attendre la revue du premier passage avant d'utiliser `--consistency`. Examiner aussi dans le rapport original H-C03/H-C04 pour les promesses de recherche par quartier, H-D03/H-L01 pour les mécanismes écologiques non étayés et H-B04 pour l'aide à encaisser alors que la demande portait sur payer. Ces observations proviennent d'une relecture de développement, pas d'une annotation indépendante ; la feuille de revue humaine demeure nécessaire.
