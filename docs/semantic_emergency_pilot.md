# Pilote local de classification d'urgence

Entraînement : les 24 cas du jeu de développement. Évaluation sur les 40 cas figés de `territory_emergency_holdout_40.json`. Modèle TF-IDF de caractères (2 à 5 grammes) et régression logistique. Aucun poids téléchargé. `combined` est l'union du détecteur lexical et du classifieur.

Le seuil initial de 0,5 a été évalué sur ce panel. À la demande du projet, le seuil du pilote est maintenant **0,48**, choisi après lecture des résultats du même panel : ce panel n'est donc plus un test indépendant du seuil. Il faudra évaluer ce réglage sur de nouveaux cas non consultés avant toute intégration à l'agent.

| Variante | TP | FN | FP | TN |
| --- | ---: | ---: | ---: | ---: |
| Lexical seul | 1 | 19 | 1 | 19 |
| Sémantique léger (0,48) | 20 | 0 | 8 | 12 |
| Union des deux (0,48) | 20 | 0 | 8 | 12 |

Commande : `python -m experiments.eval_semantic_emergency --out runs/semantic_emergency_pilot.json`. Installer `scikit-learn` séparément pour ce pilote ; il n'est pas une dépendance de l'agent de production. Ce score ne valide ni le seuil ni l'usage médical : les deux jeux sont rédigés par la même équipe, petits, non indépendants et non représentatifs. Le modèle n'est **pas connecté à l'agent**. Un abaissement du seuil à 0,35 détecte les 20 urgences mais bloque aussi les 20 cas bénins.
