# Pilote RAG intégré de développement

Ce lot regroupe les 11 passages UNESCO découpés par phrase et le résumé économique Banque mondiale dans un corpus de 12 passages. Les entrées conservent leurs propres attributions et licences ; le résumé économique est une valeur datée et révisable, pas une source d'informations en temps réel. Se référer aux métadonnées et documents de licence avant redistribution.

Le jeu contient 16 questions : huit sur les descriptions UNESCO et une sur le PIB total, quatre questions pratiques non documentées, une question sur le PIB par habitant non documenté et deux demandes d'invention. Ces cas réutilisent les pilotes existants : ils ne sont pas indépendants, ne mesurent pas toute la robustesse ou l'agent avec ses outils et ne couvrent pas les injections dans un document. Les questions de génération et les sources seront envoyées au service Azure de chat.

```powershell
.\.venv\Scripts\python.exe -m experiments.document_rag_batch --corpus data/rag_integrated_dev.json --cases data/rag_integrated_dev_cases.json
```

Jusqu'à 48 tentatives d'appel au modèle chat, retries inclus. Aucun plafond financier ; coûts potentiels même en cas d'échec. Le contrôle lexical existant porte sur les passages ; Prompt Shields n'est pas activé par défaut. La campagne s'arrête sur une erreur fournisseur et conserve un rapport partiel. Les identifiants de citation et les drapeaux d'abstention sont vérifiés automatiquement ; la pertinence de chaque citation, la fidélité des affirmations, l'incertitude et les éventuelles inventions exigent une relecture humaine. Aucun poids local ni nouvel appel embeddings.
