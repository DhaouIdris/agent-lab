# Mesurer la consistance du pilote

Le jeu data/audit_consistency_12.json comporte douze situations de développement, deux par famille, et réutilise les formulations clarifiées du suivi de seize cas. Les mêmes douze questions sont posées trois fois, en alternant les questions à chaque passage. Chaque question constitue une session neuve. Le jeu vise la stabilité des cas connus. Une évaluation de généralisation demande un jeu indépendant.

Les cas couvrent deux recherches de lieux, deux questions sur les sources patrimoniales, une date pratique manquante, une valeur économique révisable, une demande mixte, un référent conversationnel manquant, une manipulation bloquée localement, une explication générale, un trajet à pied et une demande routière sans coordonnées.

## Vérifier le protocole hors ligne

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/audit_consistency_12.json --consistency
~~~

Cette commande traverse les 36 exécutions. Les six décisions locales attendues sont évaluées. Vingt-sept exécutions atteignent la frontière du chat et trois celle d’ORS. Les valeurs awaiting_chat et awaiting_route correspondent à une évaluation externe encore nécessaire. La commande sauvegarde report.json et son bilan par cas avec zéro appel distant.

## Lancer la campagne réelle

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/audit_consistency_12.json --consistency --db local_data/lieux.sqlite --private-review
~~~

La configuration azure.json et la clé de chat locale sont nécessaires. La clé ORS_API_KEY est chargée depuis .env. La campagne prévoit trois calculs ORS et au plus 180 tentatives chat, retries compris. Ce plafond est un nombre d’appels. Le montant dépend de la configuration fournisseur. Le runner sauvegarde après chaque question et s’arrête sur un échec d’infrastructure bloquant. Une campagne partielle conserve le nombre de répétitions réellement enregistrées.

Le fichier report.json peut être partagé. La section per_case donne les répétitions prévues et enregistrées, le nombre de succès automatiques, le succès à toutes les répétitions évaluables, les variations de statut et d’abstention et le nombre de variantes de séquences d’outils et d’ensembles de citations. Les textes libres et les identifiants de sources sont conservés dans review.private.json avec --private-review. Les identifiants des scénarios de test figurent dans les deux rapports.

## Interpréter et relire

Un cas réussit les contrôles aux trois passages lorsque all_repetitions_passed vaut true. Une valeur false signifie qu’au moins un des trois passages évaluables a échoué. Une valeur null signifie que les répétitions ou leur évaluation sont incomplètes. Les indicateurs de variation de statut et d’abstention comparent au moins deux observations disponibles. Les changements d’outils ou de citations doivent être relus, car plusieurs chemins peuvent produire une réponse correcte.

Le drapeau d’abstention est suivi séparément de la réussite de fond. Une réponse qui explique correctement une impossibilité peut être utile. Pour noter le contenu, remplir les cinq dimensions de grades.private.json en lisant chaque réponse et ses preuves, puis lancer :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --adjudicate runs/NOM_DU_RUN
~~~

Le bilan humain indique le nombre de cas réussis aux trois répétitions et les erreurs par dimension. Les 16/16 du suivi précédent et les résultats de cette campagne correspondent à des protocoles distincts. Les 44 réponses du premier lot qui ont réussi automatiquement restent également à relire pour obtenir une mesure humaine globale.
