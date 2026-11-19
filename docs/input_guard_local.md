# Détecteur lexical local en entrée

L'agent intégré appelle `inspect_user_input` sur la question avant tout appel au modèle ou aux outils. Un signal bloque toute la requête. Ce filtre est local, sans modèle téléchargé, sans Prompt Shields et sans appel réseau. Les sources RAG et les noms du catalogue conservent leur filtre existant distinct ; les nouvelles règles ne sont pas intégrées automatiquement aux autres points d'entrée du projet.

Le détecteur utilise des motifs français et anglais ciblant certaines injonctions de changement de règles, usurpation de rôle, désactivation de contrôles, divulgation et altération de réponse. Normalisation Unicode et quelques séparations de lettres courantes sont prises en compte. Il peut rater des paraphrases, attaques encodées et contextes implicites, et bloquer des questions légitimes citant des attaques : il ne garantit ni l'absence d'injection ni la sûreté d'un agent. La validation des outils et les contrôles hors modèle restent nécessaires.

Comparer l'ancienne et la nouvelle règle hors ligne :

```powershell
.\.venv\Scripts\python.exe -m experiments.eval_input_guard
```

Un rapport JSON est enregistré dans `runs` ; il contient les identifiants et les décisions, pas le texte des exemples. Les jeux disponibles ont été écrits pour ce projet et certains ont servi à améliorer les règles : ils ne sont ni indépendants ni représentatifs. Les scores sont uniquement des mesures de développement. Le jeu de défi comprend des cas ambigus et des faux positifs ; examiner les IDs et annoter indépendamment un nouveau jeu FR/EN, y compris questions bénignes de sécurité, avant toute conclusion. Une requête non détectée sera transmise au modèle. Ne pas écrire de vrais secrets dans les exemples.
