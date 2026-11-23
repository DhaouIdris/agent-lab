# Questions naturelles : extension de développement

`data/natural_user_expansion_36.json` ajoute 36 questions nouvelles aux 24 questions du pilote précédent, sans modifier ce dernier ni ses résultats. Six cas couvrent chacun les lieux, les documents patrimoniaux, les affaires, les trajets, les demandes mixtes et les limites de sécurité. Les questions ne contiennent pas leurs attentes de preuve ou de format ; celles-ci sont dans des champs que l'agent ne reçoit pas. Les réponses exigent une relecture humaine, y compris lorsqu'elles passent les contrôles automatiques.

Ce jeu examine notamment les noms partagés (« Aboki » ne prouve pas une chaîne), les localités peu renseignées, les demandes d'horaires et d'accès actuels, les citations précises, les réservations impossibles et les requêtes légitimes mêlées à une injection. Il ne mesure pas les conversations à plusieurs tours : chaque question est isolée. Les trajets à deux coordonnées explicites utilisent ORS ; les demandes par nom de lieu ou à vélo ne donnent lieu à aucun calcul. Les huit cas marqués `consistency` peuvent être répétés trois fois, après examen de la première passe.

Pour contrôler les cas locaux sans clé ni appels réseau :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/natural_user_expansion_36.json
~~~

Pour les six premières questions, puis pour l'ensemble, utiliser **des dossiers de sortie différents** et conserver la revue privée localement :

~~~powershell
$run = "runs/natural_expansion_catalogue_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/natural_user_expansion_36.json --category catalogue --db local_data/lieux.sqlite --private-review --out $run
.\.venv\Scripts\python.exe -m experiments.readable_review $run

$full = "runs/natural_expansion_full_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/natural_user_expansion_36.json --db local_data/lieux.sqlite --private-review --out $full
.\.venv\Scripts\python.exe -m experiments.readable_review $full
~~~

La campagne complète répète les six questions du catalogue si la première étape a déjà été lancée ; cette première étape sert à vérifier le comportement avant de dépenser des appels pour le reste. Une exécution complète comprend 27 questions destinées au modèle, deux calculs ORS et sept décisions locales. Les éventuelles tentatives supplémentaires du fournisseur, la durée et le coût dépendent de l'environnement Azure et ne sont pas garantis. Les résultats `awaiting_chat` et `awaiting_route` du mode hors ligne ne constituent pas des succès. Les noms des catégories servent au rapport et au filtrage, pas à la question utilisateur.

Avant une répétition ciblée, relire les réponses et leurs sources dans `review.readable.private.md` ; le score automatique ne juge pas la véracité des faits, la pertinence des citations ou le ton. Ces scénarios sont rédigés par l'équipe après les campagnes précédentes. Ils sont un diagnostic de développement, pas un test indépendant ni une mesure représentative de l'usage réel. Toute correction ultérieure des questions doit créer un nouveau fichier versionné.
