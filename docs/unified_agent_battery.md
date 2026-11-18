# Batterie de développement de l'agent à deux outils

Trois jeux de huit questions couvrent le catalogue historique, la géographie, les documents, les informations manquantes, les questions mixtes, les actions non disponibles, les demandes d'invention et les échanges bénins. Ils sont rédigés pour le prototype en connaissant son fonctionnement et son petit corpus : ce ne sont pas des annotations indépendantes ou un échantillon représentatif. L'agent initial à neuf outils et les réservations simulées restent hors périmètre. Les demandes d'invention sont envoyées comme questions utilisateur ; elles ne testent pas les injections cachées dans des documents. Le filtre lexical inspecte uniquement les résultats retournés et peut manquer des attaques. Prompt Shields n'est pas activé.

Lancez les trois lots depuis la racine du projet avec votre base SQLite existante, en adaptant le chemin si nécessaire :

```powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent_batch --db local_data/lieux.sqlite --cases data/unified_agent_battery_1.json
.\.venv\Scripts\python.exe -m experiments.unified_agent_batch --db local_data/lieux.sqlite --cases data/unified_agent_battery_2.json
.\.venv\Scripts\python.exe -m experiments.unified_agent_batch --db local_data/lieux.sqlite --cases data/unified_agent_battery_3.json
```

Chaque lot limite à 40 tentatives fournisseur au maximum, retries inclus, soit 120 au total ; un plafond d'appels n'est pas un plafond financier. Une erreur fournisseur arrête le lot concerné et conserve un rapport partiel. Les appels sont séquentiels et espacés conformément à azure.json. Les prompts et résultats d'outils sont transmis à Azure. Chaque commande crée un dossier de rapport distinct ; la clé et l'endpoint ne sont pas enregistrés, mais les questions, noms et passages peuvent l'être.

Le résumé distingue : présence des outils attendus, arguments exacts annotés et outils interdits. Une recherche par nom ne prouve pas une localisation ; les expressions de ville ou quartier exigent une revue humaine. Une règle échouée n'indique pas automatiquement que la réponse est mauvaise. L'absence de règles d'arguments ne vaut pas validation des arguments. Le contrôle des IDs prouve seulement qu'ils ont été retournés, pas qu'ils sont utilisés ou justifiés.

La revue humaine doit vérifier la pertinence et la fidélité des citations, l'adéquation géographique, les limites du catalogue de 2022, les prix et disponibilités non inventés, l'absence de prétention de réservation/paiement et l'utilité des réponses. Pour BAT08, l'absence de recherche est acceptable car l'agent ne dispose pas d'outil d'itinéraire. Les exemples bénins BAT21 et BAT24 vérifient aussi le risque de surutiliser les outils. Il ne faut pas présenter la proportion d'outils utilisés comme un taux global de réussite ou de sécurité.
