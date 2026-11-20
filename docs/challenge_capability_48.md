# Campagne de validation des capacités de l'agent

Le fichier `data/challenge_capability_48.json` fige 48 situations formulées autrement que dans les panels précédents : huit par famille (catalogue, preuves, affaires, trajets, dialogue et sécurité). Douze questions, deux par famille, sont aussi marquées pour trois répétitions en sessions indépendantes. Les attentes ont été écrites avant tout appel Azure sur ce panel. Les libellés et exemples restent rédigés par l'équipe de développement : ce n'est ni une annotation indépendante ni un échantillon représentatif de toutes les questions possibles.

Après les campagnes du 20 novembre, la revue humaine a changé la politique produit pour H-S01 : la citation d'une instruction de contournement est arrêtée avant le modèle, même dans une question de formation. `data/challenge_capability_48_policy_v2.json` conserve les 48 questions mais modifie cette attente et son motif. Le panel initial et ses rapports restent intacts ; leurs scores 44/48 et 33/36 ne doivent pas être réécrits rétroactivement. Les nouvelles campagnes doivent nommer explicitement le fichier `policy_v2` afin de comparer des évaluations portant sur la même politique.

H-C05 et H-S02 ont déclenché `unsupported_price_or_time` : le contrôle rejetait une mention chiffrée même lorsqu'elle niait une confirmation ou illustrait une explication générale. L'agent préserve désormais les dénégations explicites, garde le blocage des horaires ou prix affirmés sans preuve et explique le motif des replis sans proposer de reformulation inutile. H-L08 perdait « du parc » lors du découpage de la demande : la partie documentaire conserve maintenant le contexte « parc » avant recherche ; si une question reste réellement imprécise, l'agent doit proposer des choix directement. Ces changements restent à vérifier sur Azure par revue des réponses, des citations et des éventuels nouveaux faux positifs. Un repli de validation est toujours distingué d'une réponse du modèle dans le rapport automatique, même lorsque sa formulation est pertinente.

La campagne `20261120T095249546255Z` a couvert 48 cas : 45 réussites automatiques, dont deux trajets directs H-T01/H-T02 échoués côté ORS (`transport_or_response`, environ 2 secondes chacun), alors que le trajet aux mêmes coordonnées H-T07 a ensuite réussi. Le diagnostic exact des anciens échecs ORS est impossible : transport et format étaient confondus. Le client routier retente désormais les interruptions temporaires ou réponses mal formées dans un délai total borné ; un échec direct est étiqueté `route_unavailable` au lieu de `model_output`. H-C05 était une réponse du modèle correctement prudente : le validateur refusait à tort la deuxième phrase « ces données ne prouvent pas l’ouverture à 9 h ». La négation est désormais reconnue, tandis qu'une ouverture affirmée sans source reste rejetée. Les anciens résultats restent figés ; une nouvelle exécution sera nécessaire pour mesurer les corrections.

Le suivi `data/challenge_route_followup_3.json` reprend **à l'identique les questions et attentes** H-C05, H-T01 et H-T02 ; seuls leurs indicateurs de répétition autorisent `--consistency` sur les trois. Après fusion du correctif, tester une fois ces trois cas avec le catalogue et les clés locaux :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --cases data/challenge_route_followup_3.json --db local_data/lieux.sqlite --private-review
~~~

Puis générer le Markdown privé avec `python -m experiments.readable_review runs/NOM_DU_RUN`, en utilisant le chemin du rapport affiché. Si les trois cas réussissent, la même commande avec `--consistency` donne trois répétitions par question (neuf exécutions) ; cela coûte des appels Azure et ORS. Le résultat local du modèle et la disponibilité d'ORS peuvent varier d'une exécution à l'autre ; comparer les statuts et les réponses, sans recalculer le score de la campagne initiale.

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

Pour une lecture humaine, créer un Markdown **privé** à partir d'un dossier de campagne, sans clé Azure ni appel réseau :

~~~powershell
.\.venv\Scripts\python.exe -m experiments.readable_review runs/NOM_DU_RUN
.\.venv\Scripts\python.exe -m experiments.readable_review runs/NOM_DU_RUN --failed-only
.\.venv\Scripts\python.exe -m experiments.readable_review runs/NOM_DU_RUN --case H-C05 --case H-S02
~~~

La première commande écrit `runs/NOM_DU_RUN/review.readable.private.md` : bilan, question, attente, réponse, diagnostic, contrôles en défaut, passages cités, identifiants des autres passages et cinq cases de relecture pour chaque exécution, répétitions comprises. `--all-sources` affiche aussi les textes des passages non cités ; `--failed-only` est un filtre de lecture, **pas** un nouveau score. Un fichier `review.private.json` peut aussi être donné directement à la commande, ainsi que plusieurs dossiers à la fois. Le Markdown est sensible comme le JSON privé : ne pas le publier ni le joindre à la PR. Il ne modifie ni les rapports ni la grille `grades.private.json` ; les cases cochées dans le Markdown ne sont pas importées automatiquement pour l'adjudication.

### Réponse Azure mal formée ou transport interrompu

La tentative H-C02 de la campagne `20261120T093622784336Z` a retourné une réponse d'outil, puis la tentative suivante a été classée `transport_or_format` et a arrêté la campagne à deux cas. L'ancien client mélangeait transport et format dans le même diagnostic, sans enregistrer leur distinction : impossible de déterminer rétrospectivement lequel s'est produit. Désormais, le rapport public indique uniquement `diagnostic_metadata.provider_error_kind` parmi `timeout`, `transport`, `response_json` et `response_schema` ; aucun corps de réponse, URL ni secret n'est exposé. Le client réessaie la même requête jusqu'à trois tentatives au total, avec délai borné et jitter, en respectant le délai du tour et le plafond de la campagne. Un HTTP 400 reste sans retry. Si l'échec persiste, le runner s'arrête et conserve un rapport incomplet ; il ne faut pas interpréter cet échec fournisseur comme un échec de réponse de l'agent. La relance crée une nouvelle campagne, elle ne modifie pas l'ancienne.

Les blocages avant modèle, les appels routiers non autorisés, les paiements ou réservations prétendument effectués, les valeurs actuelles inventées et les instructions de source suivies sont des incidents à examiner individuellement, même si le score agrégé est élevé. Un succès sur ces 48 cas ne certifie ni la sécurité universelle ni le déploiement en production. En cas de corrections inspirées par ce panel, conserver son premier résultat comme référence et créer ensuite de nouveaux cas non vus pour confirmer l'amélioration.
