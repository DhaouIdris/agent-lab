# Campagne de validation des capacités de l'agent

Le fichier `data/challenge_capability_48.json` fige 48 situations formulées autrement que dans les panels précédents : huit par famille (catalogue, preuves, affaires, trajets, dialogue et sécurité). Douze questions, deux par famille, sont aussi marquées pour trois répétitions en sessions indépendantes. Les attentes ont été écrites avant tout appel Azure sur ce panel. Les libellés et exemples restent rédigés par l'équipe de développement : ce n'est ni une annotation indépendante ni un échantillon représentatif de toutes les questions possibles.

| Famille | Situations couvertes |
| --- | --- |
| Catalogue | plusieurs entrées, ID exact, district manquant, fraîcheur, disponibilité, réservation et catégorie musée absente |
| Preuves | cinq documents UNESCO, citation du bon passage, tarif ou fréquentation absents, distinction entre ce qu'un texte dit et ce qu'il ne dit pas |
| Affaires | donnée Banque mondiale, révision annuelle, différence PIB/budget, événements et échéances actuels, paiement indisponible |
| Trajets | voiture, marche, coordonnées invalides ou incomplètes, classement impossible, question mixte avec trajet et injection mêlée |
| Dialogue | référent précédent manquant, réponse mixte document/catalogue, réponse partielle, refus de réservation et de proximité |
| Sécurité | cinq demandes malveillantes, dont deux mêlées à une question légitime, et quatre requêtes pédagogiques ou sur des identifiants publics |

Les identifiants documentaires exacts sont vérifiés pour treize questions et l'ID OSM exact pour une autre. La correction des faits libres, l'utilité, les promesses implicites et les nuances des refus exigent une lecture humaine. Le protocole ne mesure pas la qualité de nouvelles sources ni la généralisation à toutes les attaques.

## Vérification locale sans clé

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/challenge_capability_48.json
.\.venv\Scripts\python.exe -m experiments.audit_campaign --cases data/challenge_capability_48.json --consistency
~~~

La première vérification hors ligne a repéré cinq écarts avant correction : deux formulations de trajet non reconnues, une tentative de divulgation manquée et deux requêtes bénignes bloquées. Le prétraitement a été corrigé pour les trajets et la divulgation ; la formulation pédagogique qui cite une instruction dangereuse reste bloquée par précaution. Après correction, la campagne hors ligne visite 48 cas : 35 attendent le chat, deux attendent ORS, dix décisions locales passent et une requête bénigne est bloquée. Le sous-ensemble répété visite 36 cas : 27 attendent le chat, trois attendent d'abord le chat puis ORS, trois attendent ORS directement, trois blocages malveillants passent et trois blocages bénins échouent. Ces résultats sont un **contrôle des frontières**, pas un score de réponses du modèle. Une attaque non reconnue dans une catégorie malveillante ne sera jamais envoyée à Azure par ce runner : le résultat sera `unexpected_chat`.

## Campagne Azure et ORS

Après la PR qui ajoute ce panel et les correctifs, depuis la racine du dépôt avec la base locale, la configuration Azure et les clés dans l'environnement local :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/challenge_capability_48.json --db local_data/lieux.sqlite --private-review
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/challenge_capability_48.json --consistency --db local_data/lieux.sqlite --private-review
~~~

La première commande parcourt 48 situations une fois. La seconde répète 12 questions trois fois en alternance : **84 exécutions au total**, dont deux campagnes distinctes. Environ 62 exécutions peuvent atteindre Azure ; neuf appels ORS sont possibles si les trajets aboutissent. Le plafond est de 240 puis 180 tentatives fournisseur, retries compris, et non une estimation du nombre réellement consommé ni du prix. Le runner sauvegarde un checkpoint après chaque situation et arrête une campagne en cas d'erreur d'infrastructure bloquante. Les coûts dépendront du modèle et de la configuration Azure ; le rapport les laisse à `null` si les tarifs ne sont pas fournis.

Pour échelonner la première campagne sans changer les questions, `--category catalogue` sélectionne ses huit cas. Ce découpage produit des rapports séparés et ne constitue pas le résultat global 48/48 ; chaque sous-ensemble est identifié dans la configuration du rapport.

## Lecture et décision

Conserver `review.private.json` localement. `report.json` est la projection partageable : pas de questions, réponses, traces ni clé. Vérifier les hashes de la configuration et distinguer tout statut `provider_filtered`, `execution_error` ou `awaiting_*` d'un échec de l'agent. Comparer les résultats par famille, puis remplir les cinq dimensions de `grades.private.json` à partir des réponses et passages observés, idéalement par une personne qui n'a pas écrit le panel : complétude, faits étayés, citations pertinentes, limites exactes et absence de promesse non autorisée. Ensuite lancer `python -m experiments.audit_campaign --adjudicate runs/NOM_DU_RUN` pour chaque campagne.

Les blocages avant modèle, les appels routiers non autorisés, les paiements ou réservations prétendument effectués, les valeurs actuelles inventées et les instructions de source suivies sont des incidents à examiner individuellement, même si le score agrégé est élevé. Un succès sur ces 48 cas ne certifie ni la sécurité universelle ni le déploiement en production. En cas de corrections inspirées par ce panel, conserver son premier résultat comme référence et créer ensuite de nouveaux cas non vus pour confirmer l'amélioration.
