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

La première campagne de cinq cas a été relancée avec le prompt de la PR 49 : cinq contrôles automatiques réussis, mais la réponse Comoé ajoute encore une explication générale absente du passage cité. Ce score ne représente pas une validation humaine de toutes les phrases.

Pour mesurer la variabilité du modèle, `data/holdout_model_consistency_3.json` reprend **à l'identique** les trois questions et attentes qui passent par Azure : un seul café, Comoé et paiement. Il ajoute seulement le marqueur de répétition à la question café. Les deux trajets déterministes sont exclus de cette campagne pour éviter six appels ORS sans intérêt pour la consistance du modèle. Trois répétitions par question, en alternance, donnent neuf exécutions Azure prévues ; le nombre d'appels fournisseur peut dépasser neuf si l'agent utilise des outils ou si le fournisseur retente une requête.

```powershell
$repeat = "runs/response_consistency_$(Get-Date -Format yyyyMMddTHHmmssfff)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --consistency --cases data/holdout_model_consistency_3.json --db local_data/lieux.sqlite --private-review --out $repeat
if (Test-Path "$repeat/review.private.json") {
    .\.venv\Scripts\python.exe -m experiments.readable_review $repeat
}
```

Relire les neuf réponses pour la pertinence, la longueur et les affirmations étayées : une citation valide ne valide pas automatiquement les mécanismes écologiques. Une répétition stable de ces questions ne démontre pas une généralisation à d'autres formulations. Examiner aussi dans le rapport original H-C03/H-C04 pour les promesses de recherche par quartier, H-D03/H-L01 pour les mécanismes écologiques non étayés et H-B04 pour l'aide à encaisser alors que la demande portait sur payer. Ces observations proviennent d'une relecture de développement, pas d'une annotation indépendante ; la feuille de revue humaine demeure nécessaire.
