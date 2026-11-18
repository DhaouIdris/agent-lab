# Pilote d'agent catalogue et documents

Ce prototype relie deux outils en lecture seule dans le même tour : `search_catalogue` (SQLite historique de lieux) et `search_documents` (BM25 local). Il reçoit les résultats et leurs limites, puis produit un JSON avec les IDs de documents et lieux utilisés. Un identifiant non observé est rejeté ; cela ne valide pas la véracité de la réponse libre, la pertinence des citations ou le respect de tous les avertissements. Aucun outil de réservation, itinéraire, web, paiement ou action réelle n'est branché sur ce prototype. L'ancien laboratoire de neuf outils, avec réservations simulées, reste distinct : ce pilote ne prouve pas son intégration.

Les résultats et documents sont non fiables. Le détecteur lexical expérimental inspecte les titres/textes et noms de lieux retournés et interrompt le tour en cas de correspondance, mais ne détecte pas toutes les injections ; Prompt Shields n'est pas branché ici. Le catalogue est daté de 2022 et incomplet ; horaires, activité actuelle, prix et disponibilités ne sont pas vérifiés. Les directions et distances ne sont pas calculées.

Le pilote contient quatre questions, dont une nécessite les deux outils. La commande exige le fichier SQLite local et `azure.json`; la clé chat est saisie masquée ou lue depuis `AGENTLAB_API_KEY`. Les résultats des outils et questions sont transmis au modèle Azure. Le rapport contient les noms et textes retournés : vérifier son contenu avant partage ; il ne contient ni clé ni endpoint ni chemin de base de données.

```powershell
.\.venv\Scripts\python.exe -m experiments.unified_agent_batch --db local_data/lieux.sqlite
```

Adapter `--db` à l'emplacement réel de la base importée, sans réimporter le CSV. Pour quatre cas, maximum 20 tentatives fournisseur (retries inclus), sans plafond financier ; l'espacement et les paramètres Azure sont ceux du fichier de configuration. En cas d'erreur, le lot s'arrête et sauvegarde un rapport partiel. Si un outil est bloqué localement, ce cas reste séparé du résultat du modèle.

La métrique automatique vérifie seulement que les outils attendus ont été utilisés ; elle ne détecte pas une citation inadéquate, une hallucination, un faux horaire ou une distance inventée. Les questions sont de développement, non indépendantes, et le corpus documentaire de 12 passages reste très petit. Revue humaine et futurs tests d'injection et d'autorisation nécessaires avant toute utilisation réelle. Les tests locaux utilisent un fournisseur et un catalogue simulés ; aucun appel Azure n'a été effectué par l'auteur.
