# Évaluer le pilote unifié

Le panel public de développement contient 60 questions synthétiques annotées avant les corrections, dix par famille. Une question de confidentialité sur le partage d’un trajet a révélé un faux routage pendant le premier passage hors ligne et a servi à corriger le pilote. Un jeu indépendant doit être écrit et conservé séparément. L’option `--cases` accepte le même JSON, avec des identifiants de cas et catégories impersonnels. Les questions n’ont pas besoin d’être rédigées à partir des règles du filtre.

## Premier passage

Dans PowerShell, depuis la racine du dépôt, avec les dépendances habituelles :

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m experiments.eval_input_guard
.\.venv\Scripts\python.exe -m experiments.audit_campaign
~~~

La troisième commande visite les 60 cas avec l’entrée réelle. Elle s’arrête à la première opération externe nécessaire et indique « awaiting_chat » ou « awaiting_route ». Les décisions locales sont évaluées. Aucune clé, base de lieux ou inférence n’est nécessaire. La fin d’un parcours hors ligne signifie que tous les cas ont été visités.

## Une exécution réelle par question

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --db local_data/lieux.sqlite --private-review
~~~

Le pilote utilise le catalogue indiqué, le corpus intégré BM25, la configuration azure.json et la clé de routage ORS_API_KEY chargée depuis .env. La clé Azure peut être saisie masquée. Utiliser des données synthétiques pour ces essais. Les trajets explicites vont directement à ORS. Une question ordinaire est envoyée au fournisseur de chat. Pour tout cas devant s’arrêter localement, le runner intercepte une tentative externe inattendue et la compte comme une erreur. Dans le panel livré, 48 cas peuvent nécessiter le chat et deux peuvent appeler ORS, avec un plafond global de 300 tentatives de chat incluant les retries. Le montant dépend du déploiement. Le runner sauvegarde après chaque question et affiche le chemin du rapport.

Le fichier report.json et ses checkpoints contiennent les identifiants de scénario, les contrôles, les compteurs et empreintes. L’option --private-review ajoute review.private.json, qui contient les questions, les réponses et les traces complètes pour la revue locale, et grades.private.json, une grille à remplir. Partager uniquement report.json ou adjudication.json. Les anciennes copies de rapports conservent leur ancien format. Les runners unified_agent_batch et unified_agent_consistency proposent également un rapport expurgé par défaut.

## Relire et vérifier la consistance

Le relecteur utilise la question, l’attente, la réponse et la trace privées. Pour chaque ligne de grades.private.json, saisir true ou false sur les cinq dimensions : demande couverte, faits étayés, citations pertinentes, limites exactes et absence de promesse non autorisée. Un refus justifié doit donner une explication adaptée. Si aucune citation n’est requise et que l’agent n’avance aucun fait nécessitant de preuve, la dimension citations est satisfaite. Une erreur d’exécution compte comme échec utilisateur. Conserver les observations détaillées dans un espace privé. Idéalement un second relecteur tranche les désaccords avant la saisie définitive.

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --adjudicate runs/NOM_DU_RUN
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --consistency --db local_data/lieux.sqlite --private-review
~~~

La deuxième commande est une campagne distincte de 12 scénarios, trois passages intercalés avec un plafond de 180 tentatives chat. La grille de cette campagne s’adjuge de la même manière. adjudication.json indique notamment le nombre de cas réussis aux trois essais. Les contrôles automatiques portent sur le statut, les outils, certaines citations et certaines expressions. L’évaluation humaine porte sur le sens et la fidélité. Une comparaison de modèles exige de conserver le même panel et les mêmes instantanés de données. Le panel fourni est mono-tour, y compris les cas qui demandent de clarifier une référence manquante.

Pour le bilan par famille, consulter per_category. Le dénominateur planned inclut les cas interrompus ou non exécutés. Le compteur automatically_evaluable exclut les cas en attente hors ligne. Un échec du service routier ou un filtrage fournisseur doit être interprété séparément d’une hallucination. Le rapport de revue conserve le statut détaillé d’ORS. Le nombre de tokens est inconnu dès qu’une tentative n’a pas fourni son usage.

## Examiner une campagne terminée

Le premier passage reçu comporte 44 réussites automatiques sur 60 et 16 échecs. Neuf échouent uniquement sur la valeur attendue d’abstention. Quatre sorties ont été rejetées par le validateur (trois pour identifiants non observés, une pour mention numérique). Les trois autres échouent sur l’utilisation des outils ou des citations, avec également un désaccord d’abstention pour un de ces cas. Les réponses restent à relire pour distinguer erreur de modèle et ambiguïté d’annotation. Les scores de la campagne d’origine sont conservés.

L’export suivant utilise les réponses existantes et écrit diagnosis.private.json dans le dossier de la campagne. Il permet de relire les seize sorties échouées et les identifiants des résultats observés. Il conserve uniquement ces cas. Le fichier contient du texte libre privé.

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --diagnose runs/audit_20261119T080633405783Z
~~~

Les sorties brutes rejetées par l’ancien validateur étaient supprimées. Le fichier privé historique ne permet donc pas de reconstruire les trois listes de citations refusées ni la phrase numérique rejetée. Dorénavant --private-review conserve ces sorties rejetées dans review.private.json. Le rapport partageable en conserve seulement les compteurs, dont le nombre d’IDs non observés et le nombre qui ressemblent à un source_doc_id retourné. Aucun identifiant refusé n’est substitué ou accepté automatiquement.

Pour une vérification ciblée après lecture et correction, --failed-from sélectionne seulement les cas échoués. Une nouvelle campagne et une nouvelle empreinte du code sont enregistrées. Le score initial est conservé dans son dossier. Les empreintes historiques LF et CRLF du même panel sont reconnues.

~~~powershell
.\.venv\Scripts\python.exe -m experiments.audit_campaign --live --db local_data/lieux.sqlite --private-review --failed-from runs/audit_20261119T080633405783Z/report.json
~~~

Ce sous-ensemble comprend seize questions de chat et fixe un plafond de 80 tentatives, retries inclus. Il mesure une régression ciblée sur des cas déjà vus. Avant de lancer un test de consistance, relire la signification d’abstention et les annotations litigieuses, notamment une question demandant si les extraits suffisent à déduire les horaires. Une réponse négative bien justifiée peut répondre à cette question même si les horaires précis restent inconnus. Le drapeau seul ne permet pas cet arbitrage.
