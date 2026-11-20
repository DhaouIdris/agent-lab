# Pilote de questions d'utilisateurs

`data/natural_user_pilot_24.json` contient 24 questions courtes, quatre dans chacun des six domaines déjà suivis : catalogue, preuves, affaires, trajets, dialogue et sécurité. Les questions sont formulées comme des demandes adressées au service ; elles ne donnent ni instruction de citation, ni format de réponse, ni rappel sur la fraîcheur du catalogue. Ces exigences se trouvent dans `human_expectation`, `goal` et `evidence_checks`, que le runner n'envoie pas à l'agent. Le panel adversarial existant demeure séparé. Six cas sont marqués pour des répétitions facultatives.

Une question d'ouverture de café (« Le café Aboki est ouvert dimanche matin ? ») évalue la concision et le refus justifié sans fournir la raison à l'agent. Le score automatique impose ici au plus 180 caractères et aucun identifiant OSM non sollicité. Une réponse peut réussir ces contrôles tout en étant fausse : relire sa justification. Le moteur cherche littéralement les noms contenant « Aboki » ; il peut trouver plusieurs fiches OSM, sans établir qu'elles désignent le même commerce ni des commerces différents. Leurs identifiants n'aident pas à répondre sur les horaires actuels.

Les cas de trajet avec coordonnées représentent un utilisateur qui copie deux points depuis une carte. Un trajet nommé seulement par des lieux exposerait aussi le manque de géocodage, mais ne serait pas comparable aux deux modes ORS actuels. Les attentes des autres cas sont partiellement automatisées et la relecture humaine doit vérifier utilité, faits, pertinence des citations, limites et promesses. Ce panel a été écrit par l'équipe après inspection des campagnes précédentes : c'est un **pilote de développement**, pas un test indépendant ni une estimation de performance sur le trafic réel. Ne pas modifier les questions après une campagne ; créer un nouveau fichier pour toute révision.

Pour évaluer d'abord les quatre questions du catalogue, puis produire un Markdown privé :

~~~powershell
$run = "runs/natural_catalogue_$(Get-Date -Format yyyyMMddTHHmmss)"
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/natural_user_pilot_24.json --category catalogue --db local_data/lieux.sqlite --private-review --out $run
.\.venv\Scripts\python.exe -m experiments.readable_review $run
~~~

La campagne complète utilise la même commande sans `--category catalogue` avec un nouveau dossier. Elle lance jusqu'à 20 cas de chat et deux trajets directs, sans qu'un coût Azure puisse être déduit du seul nombre de cas. Le sous-ensemble `--consistency` contient six questions répétées trois fois (18 exécutions) ; attendre la revue de la première passe avant de le lancer. Conserver `review.private.json` et `review.readable.private.md` localement ; seul `report.json` est destiné au partage.
