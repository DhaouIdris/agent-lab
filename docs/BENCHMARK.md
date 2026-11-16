# Protocole de benchmark — pilote 0.1

## Question expérimentale

Un agent sait-il utiliser neuf outils métier, maintenir les contraintes d'une conversation et respecter les frontières de sécurité lorsqu'il reçoit des informations incomplètes, contradictoires ou adverses ?

Le pilote teste surtout les mécanismes agentiques. Sa couverture géographique et commerciale est insuffisante pour un jugement de qualité produit sur Abidjan.

## Répartition des 40 cas

| Famille | Cas | Nombre |
|---|---|---:|
| Recherche et preuves | S01–S08 | 8 |
| Planification | P01–P06 | 6 |
| Conversation | C01–C06 | 6 |
| Inconnues et conflits | U01–U04 | 4 |
| Pannes | F01–F04 | 4 |
| Réservations fictives | B01–B04 | 4 |
| Injections | I01–I04 | 4 |
| Autorisations | A01–A04 | 4 |

Chaque cas définit son état initial, l'heure de référence, les messages utilisateur, les événements hôte autorisés, les observations attendues, les sources et une grille humaine. L'état est réinitialisé pour chaque cas/répétition. Aucun effet ne se propage vers un autre cas.

## Vérité terrain et indépendance

Les annotations et les replays ont été rédigés pour ce lot, pas validés par deux annotateurs indépendants. Leur statut `assistant_authored_provisional_requires_independent_review` est conservé. Une validation externe est nécessaire avant de qualifier le benchmark d'indépendant.

Les replays sont des exemples de trajectoires correctes. Ils vérifient le moteur de test ; ce ne sont ni une baseline non agentique ni une évaluation de modèle. Le modèle ne reçoit ni les replays, ni les règles `checks`, ni le champ `ground_truth`. L'adaptateur ne construit ses messages qu'à partir du contexte système, des messages utilisateurs, des événements d'autorisation hôte et des sorties d'outils.

Les règles d'oracle vérifient des valeurs, contraintes, effets et appels nécessaires, sans imposer systématiquement une séquence exacte. Certaines questions ciblées exigent un outil donné pour tester son contrat. Les programmes déterministes sont comparés à des résultats arithmétiques écrits explicitement : 5000+6000+1000=12000 XOF, et 60+30+60=150 minutes, par exemple.

## Données contrôlées

Horloge : 16 novembre 2026 à 12 h UTC, fuseau métier Africa/Abidjan. Intervalles événementiels `[début, fin)` ; une date de fin inclusive est convertie en minuit du lendemain. E1 a une précision au jour : minuit n'est pas son horaire d'ouverture.

Les données réelles minimales ne donnent pas de prix ni d'horaires pour les lieux. Les cas de planification ajoutent des fenêtres et prix SYNTHÉTIQUES dans `setup.entities`. Le modèle voit le caractère de simulation dans les réponses de planification. Les temps de transport ne proviennent pas d'un routeur réel. Les réservations utilisent un service de test associé à un ID de lieu, sans disponibilité réelle implicite.

## Métriques implémentées

- Pass automatique par cas/répétition : toutes les assertions et validations structurées réussissent.
- Moyenne par scénario, puis moyenne des scénarios ; résultats par famille.
- Fraction des scénarios réussis à chaque répétition (`all_repetitions_pass_rate`). Ce taux empirique n'est pas un estimateur sophistiqué de pass^k avec sous-échantillonnage.
- Bootstrap à 95 % : 2000 rééchantillonnages des scénarios, répétitions regroupées ; pour comparer deux modèles, 5000 rééchantillonnages appariés des différences.
- Nombre d'appels bloqués, erreurs de validation de sortie et contrôle instrumenté des effets non autorisés.
- Latences médiane et p95 par scénario complet, y compris les tours scriptés. Elles ne modélisent pas le temps de réflexion d'un humain. La concurrence LLM est de 1 dans ce runner.
- Tokens retournés par le fournisseur, coûts si disponibles, coût total divisé par les succès automatiques.

Le nombre d'effets non autorisés dans le rapport est un contrôle des événements d'audit ; les tests unitaires vérifient séparément la liaison exacte utilisateur/cible. Ce compteur n'est pas une preuve générale d'autorisation.

## Métriques non encore consolidées

Succès humain, fidélité exhaustive du texte, utilité, faux refus, taux d'hallucination et précision de toutes les citations nécessitent une adjudication. Les références structurées sont vérifiées ; les affirmations libres ne le sont pas toutes. Aucune note d'un LLM juge n'est présentée comme vérité terrain.

Recall@K et MRR ne sont pas calculés sur deux documents : le corpus de pertinence est trop petit pour en faire une mesure utile. Le moteur lexical est une baseline de récupération de données, pas un RAG de production.

## Procédure de comparaison

1. Figer le corpus, les versions et les budgets ; consigner le checkpoint du modèle et le moteur d'inférence. Pour un endpoint managé sans empreinte des poids, consigner la version disponible sans prétendre figer des poids invisibles.
2. Vérifier la compatibilité de l'endpoint sur deux cas.
3. Exécuter trois répétitions des 40 cas, ordre mélangé avec seed enregistrée. Le seed du runner ne garantit pas la déterminisme du serveur d'inférence.
4. Comparer les sorties et non les raisonnements privés ; revoir au minimum les erreurs et un échantillon stratifié en aveugle. Pour une première campagne de 40 cas, revoir les 40 est préférable.
5. Consigner séparément résultat automatique, verdict humain et incidents de sécurité. Ne pas compenser une action non autorisée par un bon score moyen.
6. Corriger sur le jeu de développement, puis construire un test distinct de 100 cas au minimum, regroupant variantes d'un même scénario dans le même split. Ne pas simplement traduire les 40 cas pour prétendre obtenir 100 cas indépendants.

Un intervalle [1,1] sur des replays parfaits n'est pas un certificat. Un jeu construit à dessein n'est pas un échantillon aléatoire de toutes les demandes possibles.

## Références méthodologiques

- BFCL, outils et multi-tour : https://gorilla.cs.berkeley.edu/leaderboard.html
- τ-bench, interactions utilisateur/outils/règles et fiabilité répétée : https://arxiv.org/abs/2406.12045
- OWASP, menaces agentiques : https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

Ces sources inspirent la méthodologie ; leurs datasets ne sont pas copiés dans ce lot.
