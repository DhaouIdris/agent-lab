# Pilote : extraits documentaires et réponses sourcées

`rag_corpus_licensed_pilot.json` conserve les dix annotations de développement et ajoute trois extraits provenant des descriptions UNESCO de Grand-Bassam, Taï et Comoé. Les pages indiquent que ces descriptions sont disponibles sous licence CC BY-SA IGO 3.0 ; chaque entrée donne titre, éditeur, URL, date de consultation et lien de licence. Ce sont de courts extraits, pas les documents complets ; conserver ces attributions et vérifier les conditions applicables avant réutilisation. Les dates de consultation ne prouvent pas l'actualité des informations.

Une consigne demande au modèle de ne pas avancer d'exemples de pièces, procédures, tarifs ou critères non étayés. C'est une instruction au modèle, qui ne garantit pas le respect. Les quatre cas de `rag_licensed_pilot_cases.json` sont exploratoires et créés en connaissant le corpus ; le dernier reprend la question SARL du rapport RL061. Les annotations ne sont pas indépendantes.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_corpus_licensed_pilot.json --cases data/rag_licensed_pilot_cases.json
```

La commande utilise `azure.json`, un modèle chat Azure et la clé saisie masquée (ou `AGENTLAB_API_KEY`). Jusqu'à 12 tentatives chat, retries inclus, peuvent être facturées ; le coût n'est pas calculé. Le contrôle automatique ne juge pas la fidélité du texte et ne détecte pas les exemples non sourcés ; une revue humaine est nécessaire. Le rapport peut contenir passages et réponses.

Le CEPICI publie une [liste pour l'entreprise individuelle](https://cepici.gouv.ci/web/docs/liste-des-pieces-a-fournir.pdf) ; elle ne doit pas être présentée comme une liste pour une SARL. Date et régime applicables doivent être vérifiés. Pour constituer un corpus substantiel, vérifier les droits et la fraîcheur d'autres sources ; ces trois extraits n'en constituent qu'un début.
